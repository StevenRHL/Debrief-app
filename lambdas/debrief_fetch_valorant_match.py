"""debrief-fetch-valorant-match — serves a spoiler-free VALORANT decision scenario.

SCAFFOLD / NOT DEPLOYED. Same shared-function pattern as the F1 fetch Lambda,
plus the two-source design the roadmap calls for:

  MOCK_MODE=true  -> serves the curated fixture scenario from data/scenarios/
                     (realistic fake match + round data, zero network, no key).
  real mode       -> pulls the signed-in user's recent matches from HenrikDev
                     (HENRIKDEV_API_KEY), picks a gradable decision round, builds
                     a scenario in the same presented/ground_truth split, and
                     caches it (debrief-match-cache in AWS; data/scenarios/
                     locally) so debrief-grade-attempt can load it by id.

The provider is behind one function (`_fetch_recent_matches`) so the eventual
swap from HenrikDev to the official Riot API (RIOT_CLIENT_ID/SECRET, once the
production key is approved) changes that function only — same interface, same
scenario builder, per the roadmap's "build the interface generically" note.

Critical invariant (same as F1): the response contains ONLY presented_to_user
plus safe metadata. ground_truth / verified_data_points never reach the client.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make `shared` importable

PROJECT_ROOT = Path(os.environ.get("DEBRIEF_DATA_ROOT", Path(__file__).resolve().parents[1]))
DEFAULT_SCENARIO_ID = "valorant-mock-ascent-r14-retake"
HENRIKDEV_BASE = "https://api.henrikdev.xyz"

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


from shared.mock_mode import mock_mode  # noqa: E402


def _mock_mode() -> bool:
    # Per-domain: MOCK_MODE_VALORANT (default true); MOCK_MODE is a legacy override.
    return mock_mode("valorant")


def _load_scenario(scenario_id: str) -> dict:
    path = PROJECT_ROOT / "data" / "scenarios" / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(scenario_id)
    return json.loads(path.read_text())


# --------------------------------------------------------------------------- #
# Real path — written and correct, unused while MOCK_MODE is on.
# --------------------------------------------------------------------------- #
def _fetch_recent_matches(region: str, name: str, tag: str) -> list:
    """HenrikDev v3 by-name match history. The Riot-official swap replaces only
    this function: same (region, name, tag) in, same match-list shape out
    (normalized in `_normalize_match` if the shapes diverge)."""
    api_key = os.environ.get("HENRIKDEV_API_KEY")
    if not api_key:
        raise RuntimeError("HENRIKDEV_API_KEY not set and MOCK_MODE is off")
    url = (f"{HENRIKDEV_BASE}/valorant/v3/matches/{urllib.parse.quote(region)}/"
           f"{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}?mode=competitive&size=5")
    req = urllib.request.Request(url, headers={"Authorization": api_key,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    if payload.get("status") not in (200, None):
        raise RuntimeError(f"HenrikDev error: {payload.get('status')} {payload.get('errors')}")
    return payload.get("data", [])


def _round_snapshot(rnd: dict) -> dict:
    """Extract the decision-relevant numbers a HenrikDev round payload carries,
    with graceful fallbacks for absent fields (the API omits sections for some
    queue types). Everything the scenario presents traces back to this dict."""
    plant = (rnd.get("plant_events") or {})
    plant_time_ms = plant.get("plant_time_in_round")
    stats = rnd.get("player_stats") or []

    # Alive counts at plant, reconstructed from kill timestamps. Kill events are
    # nested per killer; each carries victim team + time. Before-plant deaths
    # reduce the victim's team count from 5.
    deaths_before_plant = {"Red": 0, "Blue": 0}
    for ps in stats:
        for kill in ps.get("kill_events") or []:
            if plant_time_ms is None or (kill.get("kill_time_in_round") or 0) <= plant_time_ms:
                victim_team = kill.get("victim_team")
                if victim_team in deaths_before_plant:
                    deaths_before_plant[victim_team] += 1

    # Team loadout values from per-player economy.
    loadout = {"Red": 0, "Blue": 0}
    for ps in stats:
        team = ps.get("player_team")
        econ = ps.get("economy") or {}
        if team in loadout:
            loadout[team] += econ.get("loadout_value") or 0

    return {
        "planted": bool(rnd.get("bomb_planted")),
        "plant_site": plant.get("plant_site"),
        "plant_time_in_round_ms": plant_time_ms,
        "planted_by_team": (plant.get("planted_by") or {}).get("team"),
        "defused": bool(rnd.get("bomb_defused")),
        "end_type": rnd.get("end_type"),
        "winning_team": rnd.get("winning_team"),
        "alive_at_plant": {t: 5 - deaths_before_plant[t] for t in deaths_before_plant}
        if plant_time_ms is not None else None,
        "team_loadout_value": loadout,
    }


def _round_gradability(rnd: dict) -> int:
    """Score how much of a genuine call a round contains. Post-plant rounds that
    were not simply won on eliminations carry a retake-or-save decision; plants
    where the defenders were outnumbered sharpen it; late rounds add score-state
    pressure. Pistol rounds (1, 13) are excluded — fixed buys, no economy call."""
    snap = _round_snapshot(rnd)
    round_no = rnd.get("round_number") or 0
    if round_no in (1, 13):
        return -1
    score = 0
    if snap["planted"]:
        score += 3
        if snap["end_type"] != "Eliminated":
            score += 2  # the round was decided by clock/defuse, i.e. by a decision
        alive = snap["alive_at_plant"]
        defender = "Blue" if snap["planted_by_team"] == "Red" else "Red"
        if alive and alive.get(defender, 5) < alive.get(snap["planted_by_team"], 5):
            score += 2  # outnumbered defense at plant = classic retake-or-save
    if round_no >= 20:
        score += 1
    return score


def _pick_decision_round(match: dict) -> dict | None:
    """Choose the most gradable round in the match (see _round_gradability)."""
    rounds = [r for r in match.get("rounds", []) if _round_gradability(r) >= 0]
    if not rounds:
        return None
    best = max(rounds, key=_round_gradability)
    return best if _round_gradability(best) > 0 else rounds[len(rounds) // 2]


def _build_scenario_from_match(match: dict, rnd: dict) -> dict:
    """Assemble the presented/ground_truth split from a real match + round.
    Every number in known_facts and verified_data_points comes from the round
    payload via _round_snapshot; narrative fields are built around whichever
    facts the payload actually carried, so thin rounds still read coherently."""
    meta = match.get("metadata", {})
    snap = _round_snapshot(rnd)
    round_no = rnd.get("round_number", 0)
    scenario_id = f"valorant-{meta.get('matchid', 'unknown')}-r{round_no}"

    attacker = snap["planted_by_team"]
    defender = ("Blue" if attacker == "Red" else "Red") if attacker else None
    alive = snap["alive_at_plant"] or {}

    facts = [f"Round {round_no} of the match; spike planted: {snap['planted']}."]
    decision_framing = "the decisive moment of this round"
    if snap["planted"]:
        if snap["plant_site"]:
            facts.append(f"The spike went down on {snap['plant_site']} site"
                         + (f" at {snap['plant_time_in_round_ms'] // 1000}s into the round."
                            if snap["plant_time_in_round_ms"] is not None else "."))
        if alive and defender:
            facts.append(f"Players alive at the plant: {alive.get(defender, '?')} defending "
                         f"vs {alive.get(attacker, '?')} attacking.")
            if alive.get(defender, 5) < alive.get(attacker, 5):
                decision_framing = "the retake-or-save call facing the outnumbered defense"
            else:
                decision_framing = "the post-plant call for the defense"
        facts.append("Spike defuse takes 7 seconds (3.5 to half).")
    lv = snap["team_loadout_value"]
    if lv.get("Red") or lv.get("Blue"):
        facts.append(f"Team loadout value this round: Red {lv['Red']:,} vs Blue {lv['Blue']:,} credits "
                     "— what a lost fight feeds away, and what a save banks.")

    if snap["defused"]:
        actual = "The defense committed to the retake and defused the spike."
    elif snap["planted"] and snap["end_type"] == "Bomb detonated":
        actual = ("The spike detonated — the defense did not (or could not) complete a retake; "
                  "whether they saved or died trying is visible in the kill timeline in verified_data_points.")
    elif snap["planted"]:
        actual = f"Post-plant round decided by: {snap['end_type']}."
    else:
        actual = f"No plant this round; decided by: {snap['end_type']}."

    return {
        "scenario_id": scenario_id,
        "domain": "valorant",
        "title": f"{meta.get('map', 'Unknown map')}, round {round_no}: "
                 + ("retake or save?" if snap["planted"] else "your call"),
        "difficulty": "medium",
        "source": {"api": "henrikdev", "match_id": meta.get("matchid"),
                   "map": meta.get("map"), "round_number": round_no,
                   "note": "Built from the signed-in user's real match data."},
        "presented_to_user": {
            "role": "You are the in-game leader for your side.",
            "situation": (f"{meta.get('map')}, round {round_no} of your match on "
                          f"{meta.get('game_start_patched', 'a recent date')}. "
                          f"Put yourself at {decision_framing}, using only the facts below — "
                          "reason forward from them, not backward from what you remember happening."),
            "known_facts": facts,
            "question": ("What was the right call at the decisive moment of this round, and why? "
                         "What are you weighing, what are you betting on, and what would make you wrong?"),
        },
        "ground_truth": {
            "actual_decision": actual,
            "actual_outcome": (f"The round was won by {snap['winning_team'] or 'unknown'} "
                               f"({snap['end_type']}). Grade the user's reasoning against the round "
                               "data — player counts, clock, loadout values — not against whether "
                               "their call matches this outcome."),
            "decision_rationale_factors": [
                "Player counts and plant state at the decisive moment"
                + (f" ({alive.get(defender)}v{alive.get(attacker)} at plant)" if alive and defender else "") + ".",
                "The clock: time remaining versus the 7-second defuse and rotation distances.",
                "Loadout value at risk: what a failed commit feeds away versus what a save banks"
                + (f" ({lv['Red']:,} vs {lv['Blue']:,} credits this round)" if lv.get("Red") or lv.get("Blue") else "") + ".",
                "Information state: known versus unknown enemy positions at the moment of the call.",
            ],
            "defensible_alternative": ("Either committing or saving can be sound here. Judge the "
                                       "attempt on whether it prices the player-count odds, the "
                                       "defuse clock, and the economy carried into the next round — "
                                       "a well-priced call in either direction beats a lucky one."),
            "common_mistakes": [
                "Vibes-only aggression with no engagement with the round's numbers.",
                "Grading their own call by the round result instead of the information available at the moment.",
                "Ignoring what the loadout value at risk does to the NEXT round's buy.",
                "No falsifier — never naming what would flip the call.",
            ],
        },
        "verified_data_points": {"round_snapshot": snap, "round": rnd},
    }


def _cache_scenario(scenario: dict) -> None:
    """Locally: write into data/scenarios so debrief-grade-attempt can load it by
    id. AWS swap: put_item into debrief-match-cache (keyed scenario_id, with a
    TTL) and point the grade Lambda's loader there."""
    path = PROJECT_ROOT / "data" / "scenarios" / f"{scenario['scenario_id']}.json"
    path.write_text(json.dumps(scenario, indent=2))


def _response(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def _spoiler_safe(scenario: dict) -> dict:
    return {
        "scenario_id": scenario["scenario_id"],
        "domain": scenario.get("domain"),
        "title": scenario.get("title"),
        "difficulty": scenario.get("difficulty"),
        "presented_to_user": scenario["presented_to_user"],
    }


def handler(event, context=None):
    """API Gateway proxy handler.
    GET ?scenario_id=...                      -> serve a cached/fixture scenario
    GET ?region=..&name=..&tag=..  (real mode) -> pull recent matches, build one
    """
    params = event.get("queryStringParameters") or {}

    if _mock_mode():
        scenario_id = params.get("scenario_id") or DEFAULT_SCENARIO_ID
        try:
            scenario = _load_scenario(scenario_id)
        except FileNotFoundError:
            return _response(404, {"error": f"scenario '{scenario_id}' not found"})
        return _response(200, _spoiler_safe(scenario))

    # Real mode: explicit scenario_id serves from cache; otherwise build fresh.
    if params.get("scenario_id"):
        try:
            return _response(200, _spoiler_safe(_load_scenario(params["scenario_id"])))
        except FileNotFoundError:
            return _response(404, {"error": f"scenario '{params['scenario_id']}' not found"})

    region, name, tag = params.get("region"), params.get("name"), params.get("tag")
    if not (region and name and tag):
        return _response(400, {"error": "region, name and tag are required in real mode"})
    try:
        matches = _fetch_recent_matches(region, name, tag)
    except RuntimeError as e:
        return _response(502, {"error": str(e)})
    for match in matches:
        rnd = _pick_decision_round(match)
        if rnd:
            scenario = _build_scenario_from_match(match, rnd)
            _cache_scenario(scenario)
            return _response(200, _spoiler_safe(scenario))
    return _response(404, {"error": "no gradable round found in recent matches"})


if __name__ == "__main__":
    os.environ.setdefault("MOCK_MODE", "true")
    print(json.dumps(handler({"queryStringParameters": None}), indent=2))
