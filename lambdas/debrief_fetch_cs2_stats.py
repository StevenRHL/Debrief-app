"""debrief-fetch-cs2-stats — serves a spoiler-free CS2 decision scenario.

SCAFFOLD / NOT DEPLOYED. Same shared-function pattern as the F1 and VALORANT
fetch Lambdas:

  MOCK_MODE=true  -> serves the curated fixture scenario from data/scenarios/
                     (realistic fake stats, zero network, no key).
  real mode       -> pulls the signed-in user's profile/segment stats from the
                     official tracker.gg CS:GO/CS2 API (TRACKERGG_APP_ID as the
                     TRN-Api-Key header), builds an economy-decision scenario in
                     the same presented/ground_truth split, and caches it so
                     debrief-grade-attempt can load it by id.

tracker.gg's public API exposes aggregate profile/segment stats rather than
round-by-round demos, so the real-mode scenario builder frames the decision
around the player's own tendencies (win rates, economy patterns) — the fixture
shows the richer target shape a demo-parsing data source would enable later.

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
DEFAULT_SCENARIO_ID = "cs2-mock-mirage-r21-eco"
TRACKERGG_BASE = "https://public-api.tracker.gg/v2/csgo/standard"

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


from shared.mock_mode import mock_mode  # noqa: E402


def _mock_mode() -> bool:
    # Per-domain: MOCK_MODE_CS2 (default true); MOCK_MODE is a legacy override.
    return mock_mode("cs2")


def _load_scenario(scenario_id: str) -> dict:
    path = PROJECT_ROOT / "data" / "scenarios" / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(scenario_id)
    return json.loads(path.read_text())


# --------------------------------------------------------------------------- #
# Real path — written and correct, unused while MOCK_MODE is on.
# --------------------------------------------------------------------------- #
def _fetch_profile_stats(steam_id: str) -> dict:
    """Official tracker.gg CS:GO/CS2 profile stats for a Steam ID."""
    app_id = os.environ.get("TRACKERGG_APP_ID")
    if not app_id:
        raise RuntimeError("TRACKERGG_APP_ID not set and MOCK_MODE is off")
    url = f"{TRACKERGG_BASE}/profile/steam/{urllib.parse.quote(steam_id)}"
    req = urllib.request.Request(url, headers={"TRN-Api-Key": app_id,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    if "errors" in payload:
        raise RuntimeError(f"tracker.gg error: {payload['errors']}")
    return payload.get("data", {})


def _extract_overview(data: dict) -> dict:
    """Pull the overview segment's stat values (tracker.gg wraps each stat in a
    {value, displayValue, ...} object). Missing segments yield an empty dict."""
    for seg in data.get("segments", []):
        if seg.get("type") == "overview":
            return {k: v.get("value") for k, v in seg.get("stats", {}).items()
                    if isinstance(v, dict)}
    return {}


def _build_scenario_from_stats(steam_id: str, data: dict) -> dict:
    """Assemble a tendency-based economy scenario from profile stats.

    tracker.gg exposes aggregates, not rounds, so the scenario's FRAME (the
    round state: score, banks, loss bonus) is a standard textbook economy
    decision clearly labeled as constructed — while the player's own tracked
    numbers are woven in as the evidence to reason with. The split keeps the
    honesty line clean: constructed frame, real tendencies, and the grader is
    told which is which. The structure matches the fixtures exactly, so grading
    and the frontend are identical across data sources."""
    overview = _extract_overview(data)
    scenario_id = f"cs2-{steam_id}-economy"

    win_pct = overview.get("wlPercentage")
    kd = overview.get("kd")
    dpr = overview.get("damagePerRound")
    hs_pct = overview.get("headshotPct")

    facts = [
        # The constructed frame — the same numbers for every player, labeled as such.
        "Round 17 of 24 (MR12), you are T side down 6–10 after losing a gun round. "
        "Team bank: 2,100–3,300 credits each — a force now means Galils/MAC-10s and "
        "half utility into likely full CT rifle buys with kits.",
        "Loss bonus is at 2,900 credits: conceding one more round funds a full buy — "
        "rifles, armor, and a complete utility set — for every remaining round.",
        "Losing a force resets the loss bonus to 1,400 and makes round 19 a forced eco "
        "into what could be match point.",
    ]
    # The player's own tracked numbers — the evidence to reason with.
    if win_pct is not None:
        facts.append(f"Your tracked match win rate is {win_pct:.0f}% — you win close games "
                     "at roughly the rate you keep your economy intact.")
    if kd is not None and dpr is not None:
        facts.append(f"Your tracked K/D is {kd:.2f} at {dpr:.0f} damage per round — "
                     "price honestly whether SMG rounds against rifles play to that profile.")
    elif kd is not None:
        facts.append(f"Your tracked K/D is {kd:.2f} — price honestly whether SMG rounds "
                     "against rifles play to that profile.")
    if hs_pct is not None:
        facts.append(f"Your tracked headshot rate is {hs_pct:.0f}% — relevant to whether "
                     "a Galil at range or a MAC-10 up close is the realistic force plan.")

    return {
        "scenario_id": scenario_id,
        "domain": "cs2",
        "title": "Down 6–10, broken economy: force or full eco?",
        "difficulty": "medium",
        "source": {"api": "trackergg", "steam_id": steam_id,
                   "note": ("Round frame is a constructed textbook economy decision (tracker.gg "
                            "exposes aggregate stats, not rounds); the tendency numbers are the "
                            "player's real tracked stats.")},
        "presented_to_user": {
            "role": "You are calling the buys for your side.",
            "situation": ("An economy decision built around your own tracked tendencies. The round "
                          "state below is a standard constructed frame; the performance numbers are "
                          "yours. Make the call as if it's your match."),
            "known_facts": facts,
            "question": ("Force-buy or full eco? Explain your call — what are you weighing, "
                         "what are you betting on, and what would make you wrong?"),
        },
        "ground_truth": {
            "actual_decision": ("Constructed frame — there is no single recorded outcome. Grade "
                                "against sound economy reasoning: at max-minus-one loss bonus with "
                                "8 rounds left, the eco line guarantees full buys for every "
                                "remaining round while the force risks compounding into an eco at "
                                "match point."),
            "actual_outcome": ("No recorded round to reveal. The economy math itself is the ground "
                               "truth: conceding round 17 banks a guaranteed full-buy run; a failed "
                               "force (~2,700 spent into full rifles) typically prices at 20–30% "
                               "and resets the loss bonus. Grade the pricing, not a result."),
            "decision_rationale_factors": [
                "Loss-bonus mechanics: at 2,900 one more concession fully funds the rest of the map; "
                "a failed force resets it to 1,400 and cascades.",
                "Sequencing: what a failed force does to round 19 — an eco into potential match point.",
                "The player's own tracked numbers: whether their K/D, damage per round, and win rate "
                "support beating full rifle buys with SMGs and half utility.",
                "The one honest case for the force: CTs often spend down after two won gun rounds — "
                "if their buy is thin, force equity rises above the baseline.",
            ],
            "defensible_alternative": ("The force is defensible if it is priced, not hoped: the user "
                                       "should name the ~20–30% baseline, the specific read that "
                                       "raises it (thin CT buy, map control plan, their own close-"
                                       "range profile), and what a failed force costs the next two "
                                       "rounds. An eco call is defensible by default here; grade it "
                                       "on whether the sequencing math is actually engaged rather "
                                       "than asserted."),
            "common_mistakes": [
                "Panic forcing with no sequence math — treating being down four as the emergency, "
                "when the broken economy is the emergency.",
                "Ignoring loss-bonus mechanics entirely.",
                "Citing their own aggregate stats as confidence rather than evidence — a high K/D "
                "does not reprice SMGs into rifles without a range/utility argument.",
                "No falsifier: never naming the CT-side read that would justify the force.",
            ],
        },
        "verified_data_points": {
            "note": ("trackergg_overview values are the player's real tracked aggregates; the "
                     "economy frame numbers (banks, loss bonus, round state) are constructed and "
                     "labeled as such in the source note."),
            "constructed_frame": {
                "round": 17, "format": "MR12", "score": "6-10", "side": "T",
                "team_bank_range_credits": [2100, 3300], "loss_bonus_credits": 2900,
                "loss_bonus_after_failed_force": 1400,
                "typical_failed_force_equity": [0.20, 0.30],
            },
            "trackergg_overview": overview,
        },
    }


def _cache_scenario(scenario: dict) -> None:
    """Locally: write into data/scenarios so debrief-grade-attempt can load it by
    id. AWS swap: put_item into debrief-match-cache (keyed scenario_id, TTL)."""
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
    GET ?scenario_id=...                 -> serve a cached/fixture scenario
    GET ?steam_id=...       (real mode)  -> pull tracker.gg stats, build one
    """
    params = event.get("queryStringParameters") or {}

    if _mock_mode():
        scenario_id = params.get("scenario_id") or DEFAULT_SCENARIO_ID
        try:
            scenario = _load_scenario(scenario_id)
        except FileNotFoundError:
            return _response(404, {"error": f"scenario '{scenario_id}' not found"})
        return _response(200, _spoiler_safe(scenario))

    if params.get("scenario_id"):
        try:
            return _response(200, _spoiler_safe(_load_scenario(params["scenario_id"])))
        except FileNotFoundError:
            return _response(404, {"error": f"scenario '{params['scenario_id']}' not found"})

    steam_id = params.get("steam_id")
    if not steam_id:
        return _response(400, {"error": "steam_id is required in real mode"})
    try:
        data = _fetch_profile_stats(steam_id)
    except RuntimeError as e:
        return _response(502, {"error": str(e)})
    scenario = _build_scenario_from_stats(steam_id, data)
    _cache_scenario(scenario)
    return _response(200, _spoiler_safe(scenario))


if __name__ == "__main__":
    os.environ.setdefault("MOCK_MODE", "true")
    print(json.dumps(handler({"queryStringParameters": None}), indent=2))
