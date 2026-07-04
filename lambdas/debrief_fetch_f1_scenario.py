"""debrief-fetch-f1-scenario — serves a spoiler-free F1 decision scenario.

SCAFFOLD / NOT DEPLOYED. Locally this reads the scenario JSON from the repo's
data/ directory. In AWS it would read from the `debrief-f1-scenarios` DynamoDB
table instead; only the `_load_scenario` body changes.

Critical invariant: the response contains ONLY `presented_to_user` plus safe
metadata. `ground_truth` and `verified_data_points` are grader-only and must
never reach the client, or the scenario is spoiled.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make `shared` importable

PROJECT_ROOT = Path(os.environ.get("DEBRIEF_DATA_ROOT", Path(__file__).resolve().parents[1]))
DEFAULT_SCENARIO_ID = "monza-2024-leclerc-onestop"

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _load_scenario(scenario_id: str) -> dict:
    """Local scaffold loader. AWS version would DynamoDB get_item on
    debrief-f1-scenarios keyed by scenario_id."""
    path = PROJECT_ROOT / "data" / "scenarios" / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(scenario_id)
    return json.loads(path.read_text())


def _response(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def handler(event, context=None):
    """API Gateway proxy handler. GET, optional ?scenario_id=..."""
    params = event.get("queryStringParameters") or {}
    scenario_id = params.get("scenario_id") or DEFAULT_SCENARIO_ID

    try:
        scenario = _load_scenario(scenario_id)
    except FileNotFoundError:
        return _response(404, {"error": f"scenario '{scenario_id}' not found"})

    # Spoiler-safe projection — ground_truth / verified_data_points intentionally omitted.
    payload = {
        "scenario_id": scenario["scenario_id"],
        "domain": scenario.get("domain"),
        "title": scenario.get("title"),
        "difficulty": scenario.get("difficulty"),
        "presented_to_user": scenario["presented_to_user"],
    }
    return _response(200, payload)


if __name__ == "__main__":
    # Quick manual check: python3 lambdas/debrief_fetch_f1_scenario.py
    print(json.dumps(handler({"queryStringParameters": None}), indent=2))
