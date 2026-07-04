"""debrief-fetch-history — a signed-in user's past attempts + progress summary.

SCAFFOLD / NOT DEPLOYED. In mock mode this GENERATES a deterministic, realistic
attempt history from the user_id (same user always sees the same history), so
the progress view is fully demoable with zero storage. In real mode it queries
the `debrief-attempts` DynamoDB table — that path is written below and correct,
just unused while MOCK_MODE is on.

Route:
    GET /history    Authorization: Bearer <token>
    -> {user_id, attempts: [...], summary: {attempt_count, average_score,
        score_trend, weakest_dimension, per_dimension_averages, by_domain}}
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make `shared` importable

from shared import auth  # noqa: E402
from shared.grading import DIMENSIONS  # noqa: E402

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}

TABLE_PREFIX = os.environ.get("DYNAMODB_TABLE_PREFIX", "debrief-")

# Scenario pool the mock generator draws from — ids/titles match real local
# scenario files where they exist so the UI can link through.
_MOCK_SCENARIO_POOL = [
    ("f1", "monza-2024-leclerc-onestop", "Monza 2024: Cover McLaren or commit to the one-stop?"),
    ("f1", "monza-2024-leclerc-onestop", "Monza 2024: Cover McLaren or commit to the one-stop?"),
    ("valorant", "valorant-mock-ascent-r14-retake", "Ascent, round 14: retake B or save?"),
    ("valorant", "valorant-mock-ascent-r14-retake", "Ascent, round 14: retake B or save?"),
    ("cs2", "cs2-mock-mirage-r21-eco", "Mirage, round 21: force-buy or full eco?"),
]


from shared.mock_mode import mock_mode  # noqa: E402


def _mock_mode() -> bool:
    # History spans all domains, so it isn't tied to one game flag: mock unless
    # the legacy MOCK_MODE override is explicitly off.
    return mock_mode()


# --------------------------------------------------------------------------- #
# Mock history generation — deterministic per user, improving over time so the
# progress chart has a story to tell.
# --------------------------------------------------------------------------- #
def _generate_mock_history(user_id: str) -> list:
    rng = random.Random(user_id)  # seeded: same user -> same history every time
    n = rng.randint(8, 14)
    now = datetime.now(timezone.utc)
    attempts = []
    # A gentle upward skill trend with one persistent weak dimension, so the
    # "weak categories" feature has something real to surface.
    weak_dim = rng.choice(["risk_score", "calibration_score"])
    for i in range(n):
        progress = i / max(n - 1, 1)  # 0 oldest -> 1 newest
        domain, scenario_id, title = rng.choice(_MOCK_SCENARIO_POOL)
        scores = {}
        for field, cap in DIMENSIONS:
            base = 0.35 + 0.45 * progress  # improves from ~35% to ~80% of cap
            if field == weak_dim:
                base -= 0.25  # the recurring blind spot
            frac = min(1.0, max(0.0, base + rng.uniform(-0.12, 0.12)))
            scores[field] = round(cap * frac)
        overall = sum(scores.values())
        if overall >= 70:
            verdict = rng.choice(["matched_history", "defensible_alternative"])
        elif overall >= 45:
            verdict = rng.choice(["defensible_alternative", "flawed_process"])
        else:
            verdict = "flawed_process"
        ts = now - timedelta(days=(n - 1 - i) * rng.uniform(1.2, 3.0), hours=rng.uniform(0, 20))
        attempts.append({
            "attempt_id": f"mock-{user_id}-{i:03d}",
            "user_id": user_id,
            "scenario_id": scenario_id,
            "scenario_title": title,
            "domain": domain,
            "timestamp": ts.isoformat(timespec="seconds"),
            "overall_score": overall,
            "verdict": verdict,
            **scores,
            "mode": "mock",
        })
    return attempts


# --------------------------------------------------------------------------- #
# Real path — DynamoDB query on debrief-attempts. Written, correct, unused in
# mock mode. boto3 imported lazily so mock mode stays stdlib-only.
# --------------------------------------------------------------------------- #
def _query_attempts_dynamodb(user_id: str) -> list:
    import boto3  # lazy
    table = boto3.resource(
        "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")
    ).Table(f"{TABLE_PREFIX}attempts")
    items, kwargs = [], {
        "KeyConditionExpression": "user_id = :u",
        "ExpressionAttributeValues": {":u": user_id},
        "ScanIndexForward": True,  # oldest first, matching the mock generator
    }
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            return items
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


# --------------------------------------------------------------------------- #
# Summary — same math over either source
# --------------------------------------------------------------------------- #
def _summarize(attempts: list) -> dict:
    if not attempts:
        return {"attempt_count": 0}
    per_dim = {}
    for field, cap in DIMENSIONS:
        avg = sum(a[field] for a in attempts) / len(attempts)
        per_dim[field] = {"average": round(avg, 1), "max": cap, "pct": round(100 * avg / cap)}
    weakest = min(per_dim, key=lambda f: per_dim[f]["pct"])
    half = max(len(attempts) // 2, 1)
    early = sum(a["overall_score"] for a in attempts[:half]) / half
    late = sum(a["overall_score"] for a in attempts[half:]) / max(len(attempts) - half, 1)
    by_domain = {}
    for a in attempts:
        d = by_domain.setdefault(a["domain"], {"attempts": 0, "total": 0})
        d["attempts"] += 1
        d["total"] += a["overall_score"]
    for d in by_domain.values():
        d["average_score"] = round(d.pop("total") / d["attempts"], 1)
    return {
        "attempt_count": len(attempts),
        "average_score": round(sum(a["overall_score"] for a in attempts) / len(attempts), 1),
        "score_trend": round(late - early, 1),  # positive = improving
        "weakest_dimension": weakest,
        "per_dimension_averages": per_dim,
        "by_domain": by_domain,
    }


def _response(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def handler(event, context=None):
    user = auth.user_from_event(event)
    if not user:
        return _response(401, {"error": "sign in to see your progress"})

    if _mock_mode():
        attempts = _generate_mock_history(user["user_id"])
    else:
        attempts = _query_attempts_dynamodb(user["user_id"])

    return _response(200, {
        "user_id": user["user_id"],
        "username": user["username"],
        "attempts": attempts,
        "summary": _summarize(attempts),
        "mode": "mock" if _mock_mode() else "real",
    })


if __name__ == "__main__":
    os.environ.setdefault("MOCK_MODE", "true")
    from shared.auth import login
    token = login("demo", "x")["token"]
    out = handler({"httpMethod": "GET", "path": "/history",
                   "headers": {"Authorization": f"Bearer {token}"}})
    body = json.loads(out["body"])
    print(json.dumps(body["summary"], indent=2))
    print(f"{len(body['attempts'])} attempts")
