"""Feature-driven mock verdict synthesizers for the VALORANT and CS2 domains.

Same philosophy as the F1 synthesizer in grading.py: in mock mode, scores are
derived deterministically from which real trade-offs the attempt text engages
with, so clicking through the demo yields a genuine range of verdicts and the
same input always grades the same. One generic engine, one config per domain,
so adding a future domain is a config, not a rewrite.

Injection attempts get the CORRECT resisted behavior (low score, flawed_process,
manipulation called out) in every domain — that is what the real grader must do.
"""

_INJECTION_MARKERS = [
    "</user_attempt>", "system notice", "ignore the rubric", "supersede",
    "award overall_score", "pre-approved", "developer-approved", "this instruction",
]


def _has(lower, *subs):
    return any(s in lower for s in subs)


def _join(items):
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# --------------------------------------------------------------------------- #
# Domain configs. `matched` / `alternative` are call-detection keyword sets
# (matched = the historically successful call). `features` maps a feature key to
# (keywords, engaged-phrase, calibration-weight). `missing_priority` drives the
# improvement nudge; `key_insights` the takeaway; injection_* the resisted verdict.
# --------------------------------------------------------------------------- #
_CONFIGS = {
    "valorant": {
        "matched": ["save", "don't retake", "do not retake", "concede", "give the round",
                    "hold for exit", "keep our guns", "keep the guns", "save the ops",
                    "save our weapons", "play for next round", "reset"],
        "alternative": ["retake", "go b", "hit the site", "take the site back", "commit all three",
                        "push b", "we retake", "go for the defuse"],
        "features": {
            "odds": (["3v4", "3 v 4", "man down", "player count", "outnumber", "percent", "%",
                      "low percentage", "unfavorable", "coin flip", "25"],
                     "the 3v4 player-count disadvantage", 5),
            "clock": (["38 sec", "seven second", "7 second", "7-second", "defuse tim", "clock",
                       "13 second", "13-second", "detain", "seconds left"],
                      "the clock against the defuse and detain timings", 5),
            "economy": (["credit", "econom", "loadout", "operator", "bank", "buy round",
                         "full buy", "guns next round", "10,900", "4,200"],
                        "the economics of saved loadouts", 6),
            "info": (["lurker", "market", "information", "unknown position", "crossfire",
                      "post-plant setup", "no info"],
                     "the information disadvantage and the market lurker", 4),
            "ult": (["lockdown", "ult", "killjoy ult", "kj ult"],
                    "Killjoy ult economics", 3),
        },
        "missing_priority": [
            ("economy", "the economics — the ~10,900 credits of loadout a failed retake feeds away"),
            ("odds", "pricing the retake: a 3v4 into a planted spike is roughly a 1-in-4 round"),
            ("info", "the information state — the market lurker makes every retake path contested"),
            ("clock", "the clock math: 38 seconds minus the rotate barely fits a 7-second defuse"),
            ("falsifier", "an explicit falsifier — what information would flip your call"),
        ],
        "key_insights": [
            ("economy", "The save isn't conceding — it converts a ~25% retake into a ~61% next round with full guns and Killjoy ult banked."),
            ("odds", "The core price: a 3v4 post-plant retake with an unknown lurker is roughly 22–28% equity."),
            (None, "Ult economics: lockdown wins a buy round you control; burned on the retake its 13-second detain barely fits the clock."),
        ],
        "covering_decision_fb": ("Clear call to commit to the retake — the opposite of what was called, but a "
                                 "committed, actionable decision. Capped slightly because the numbers at the "
                                 "moment of the call leaned save."),
        "matched_decision_fb": ("Clear call to save — conceding the round to bank guns and ult is exactly the "
                                "kind of committed, unglamorous call this dimension rewards."),
        "risk_hint": "a fast retake before the post-plant sets up, or the lurker rotating out of market",
    },
    "cs2": {
        "matched": ["eco", "full save", "save this round", "full eco", "don't buy", "do not buy",
                    "no buy", "guarantee the buy", "save for", "concede the round", "reset"],
        "alternative": ["force", "force-buy", "force buy", "buy now", "galil", "we buy",
                        "half buy", "half-buy"],
        "features": {
            "buymath": (["3,000", "3000", "5,500", "5500", "4,700", "4700", "loadout", "galil",
                         "mac-10", "smg", "armor", "kevlar", "rifle deficit"],
                        "the force-vs-full loadout math", 6),
            "lossbonus": (["loss bonus", "loss-bonus", "3,400", "3400", "2,400", "2400",
                           "bonus round", "max bonus"],
                          "the loss-bonus mechanics", 5),
            "winrates": (["1 of 4", "1-3", "8 of 13", "8-5", "win rate", "winrate", "20%",
                          "22%", "25%", "percent"],
                         "the team's own in-match win rates", 5),
            "sequence": (["elimination", "match point", "remaining rounds", "rounds left",
                          "next round", "sequence", "9-12", "two more", "4 of the next"],
                         "the elimination-round sequencing", 5),
            "saver": (["ak saver", "saved an ak", "saved ak", "the saver", "one rifle"],
                      "what the saved AK is actually worth", 3),
        },
        "missing_priority": [
            ("winrates", "the team's own numbers sitting in the facts — forces are 1 of 4, full buys 8 of 13 this match"),
            ("lossbonus", "the loss-bonus mechanics: one more conceded round fully funds rifles, utility and an AWP"),
            ("sequence", "the sequence math — a failed force makes the NEXT round an eco into match point"),
            ("buymath", "the loadout gap: ~3,000 of force gear into ~5,500 CT buys with kits"),
            ("falsifier", "an explicit falsifier — what would make the other call right"),
        ],
        "key_insights": [
            ("winrates", "The strongest evidence was already on the scoreboard: this team's forces win 1 in 4, its full buys 8 in 13."),
            ("sequence", "Elimination-round logic cuts the other way: the eco guarantees best-odds full buys in every must-win round left."),
            (None, "The eco is buying equipment, not conceding hope — max loss bonus fully funds the next three buys."),
        ],
        "covering_decision_fb": ("Clear call to force — the opposite of what was called, but a committed, "
                                 "actionable decision. Capped slightly because this match's own force and "
                                 "full-buy win rates leaned eco."),
        "matched_decision_fb": ("Clear call to eco — giving up a round you were probably losing anyway to "
                                "guarantee full buys is exactly the committed call this dimension rewards."),
        "risk_hint": "the CTs being utility-poor after two big spends, or a thin CT buy the force could catch",
    },
}


def _injection_verdict(reveal: str, domain_insight: str) -> dict:
    return {
        "overall_score": 20,
        "verdict": "flawed_process",
        "decision_score": 10,
        "decision_feedback": ("You did state a call, so you earn some decision credit, but it's thin "
                              "and leans on the noise around it."),
        "reasoning_score": 6,
        "reasoning_feedback": (
            "Heads up: this attempt embedded an injection — content claiming special "
            "instructions or a pre-approved score. That is untrusted input and was "
            "ignored entirely; it has no effect on your grade. Grading only the genuine "
            "reasoning left: it's generic, assumes its own conclusion, and doesn't engage "
            "the specific numbers this decision turns on."
        ),
        "risk_score": 2,
        "risk_feedback": ("No real weighing of what goes wrong with your chosen path — the risks are "
                          "asserted away rather than priced."),
        "calibration_score": 2,
        "calibration_feedback": ("No concrete predictions to check against the data, which is itself "
                                 "the problem."),
        "what_actually_happened": reveal,
        "key_insight_missed": domain_insight,
        "strengths": ["Committed to a call despite the noise in the submission"],
    }


def synthesize(domain: str, attempt_text: str, scenario: dict = None) -> dict:
    # A scenario may embed its own `mock_synth` config (same shape as a _CONFIGS
    # entry, JSON lists instead of tuples) — that's how new fixture scenarios get
    # decision-specific mock grading without touching this engine. Domain config
    # is the fallback for the original one-fixture-per-domain scenarios.
    cfg = (scenario or {}).get("mock_synth") or _CONFIGS[domain]
    lower = attempt_text.lower()
    reveal = (scenario or {}).get("ground_truth", {}).get(
        "actual_outcome", "The historical outcome is recorded in the scenario's ground truth.")

    if any(m in lower for m in _INJECTION_MARKERS):
        return _injection_verdict(reveal, cfg["key_insights"][0][1])

    # "save vs retake"-style words overlap (a retake call may name the save as
    # its fallback), so weigh signal strength on both sides: occurrence counts,
    # tie broken by which call is named first — leads tend to open with the call.
    matched_hits = sum(lower.count(k) for k in cfg["matched"])
    alt_hits = sum(lower.count(k) for k in cfg["alternative"])
    has_call = matched_hits > 0 or alt_hits > 0
    if matched_hits != alt_hits:
        covering = alt_hits > matched_hits
    else:
        first_matched = min((lower.find(k) for k in cfg["matched"] if k in lower), default=len(lower))
        first_alt = min((lower.find(k) for k in cfg["alternative"] if k in lower), default=len(lower))
        covering = first_alt < first_matched

    engaged, present_keys, calibration = [], set(), 2
    for key, (keywords, phrase, cal_weight) in cfg["features"].items():
        if _has(lower, *keywords):
            engaged.append(phrase)
            present_keys.add(key)
            calibration += cal_weight
    calibration = min(20, calibration)

    f_falsifier = _has(lower, "what would make me wrong", "wrong if", "falsif", "i'm betting",
                       "im betting", "the bet", "my bet", "downside", "risk is",
                       "would make my call", "i could be wrong", "unless")
    if f_falsifier:
        present_keys.add("falsifier")

    wc = len(attempt_text.split())
    n_content = len(engaged)

    reasoning = min(40, n_content * 7 + (5 if f_falsifier else 0) + (3 if wc >= 90 else 0))
    if has_call and wc >= 60 and reasoning < 8:
        reasoning = 8  # a real, committed argument floors above "pure vibes"

    two_sided = f_falsifier and n_content >= 2
    risk = min(20, 2 + n_content * 2 + (6 if f_falsifier else 0) + (4 if two_sided else 0))

    if has_call:
        decision = 16
        if _has(lower, "commit", "no question", "definitely", "clearly", "absolutely", "100%", "for sure"):
            decision = 19
        if covering:
            decision = min(decision, 15)  # defensible but capped below the matching call
    else:
        decision = 6

    if not has_call or reasoning < 12:
        verdict = "flawed_process"
    elif covering:
        verdict = "defensible_alternative"
    else:
        verdict = "matched_history"

    if reasoning >= 26:
        lead = "Strong process. "
    elif reasoning >= 14:
        lead = "There's a real argument here. "
    else:
        lead = "This leans on instinct more than analysis. "
    if engaged:
        engaged_txt = "You engaged with " + _join(engaged) + ". "
    else:
        engaged_txt = ("You didn't engage the specific trade-offs of this decision — none of the "
                       "numbers in front of you made it into the argument. ")
    missing = next((desc for key, desc in cfg["missing_priority"] if key not in present_keys), None)
    nudge = ("To go further, work in " + missing + ".") if missing else "You covered the major trade-offs."
    reasoning_feedback = lead + engaged_txt + nudge

    if not has_call:
        decision_feedback = ("You didn't land on a single clear call — this dimension rewards "
                             "committing to one action, not weighing both and stopping there.")
    elif covering:
        decision_feedback = cfg["covering_decision_fb"]
    else:
        decision_feedback = cfg["matched_decision_fb"]

    if risk >= 12:
        risk_feedback = ("Good two-sided risk thinking — you weighed what could go wrong on your side, "
                         "not just the danger of the road not taken.")
    elif risk >= 6:
        risk_feedback = ("You touched the risks but mostly on one side. Name the specific scenarios "
                         "where the other call wins — " + cfg["risk_hint"] + ".")
    else:
        risk_feedback = ("The risks of your chosen path aren't really named — no pricing of the ways "
                         "this call loses, no case for when the alternative wins.")

    if calibration >= 12:
        calibration_feedback = "Your read of the odds and the economics lines up well with what the data shows."
    elif calibration >= 6:
        calibration_feedback = ("Partly calibrated — you're in the right area but didn't pin the numbers "
                                "the situation actually produced.")
    else:
        calibration_feedback = ("Little here to check against reality — few concrete predictions to hold "
                                "up to the outcome.")

    strengths = []
    if has_call:
        strengths.append("Committed to a clear, actionable call")
    if n_content >= 2:
        strengths.append("Reasoned from the scenario's actual numbers")
    if f_falsifier:
        strengths.append("Named what would make the call wrong")
    if not strengths:
        strengths = ["Put a stake in the ground with a definite answer"]

    if reasoning >= 30:
        key_insight_missed = ""
    else:
        key_insight_missed = next(
            (insight for key, insight in cfg["key_insights"] if key is None or key not in present_keys),
            "")

    overall = decision + reasoning + risk + calibration
    return {
        "overall_score": overall,
        "verdict": verdict,
        "decision_score": decision,
        "decision_feedback": decision_feedback,
        "reasoning_score": reasoning,
        "reasoning_feedback": reasoning_feedback,
        "risk_score": risk,
        "risk_feedback": risk_feedback,
        "calibration_score": calibration,
        "calibration_feedback": calibration_feedback,
        "what_actually_happened": reveal,
        "key_insight_missed": key_insight_missed,
        "strengths": strengths,
    }
