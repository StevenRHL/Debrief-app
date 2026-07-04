"""debrief-list-scenarios — spoiler-safe index of available scenarios.

SCAFFOLD / NOT DEPLOYED. Lets the frontend offer a scenario picker per domain
instead of always serving each domain's single default. Locally this scans
data/scenarios/; in AWS it would query the debrief-scenarios table's domain GSI
(see infra/template.yaml) — only `_list_scenarios` changes.

Critical invariant (same as the fetch Lambdas): the index carries ONLY safe
metadata — id, domain, title, difficulty, mock flag. Never presented_to_user
(kept out to keep the index light), never ground_truth / verified_data_points.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make `shared` importable

PROJECT_ROOT = Path(os.environ.get("DEBRIEF_DATA_ROOT", Path(__file__).resolve().parents[1]))

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _is_mock(scenario: dict) -> bool:
    return "MOCK" in (scenario.get("source", {}).get("note") or "")


def _list_scenarios(domain: str | None) -> list[dict]:
    """Local scaffold: scan the scenarios directory. AWS swap: query the
    debrief-scenarios table (GSI on domain when a domain filter is given,
    scan otherwise) projecting the same four safe attributes."""
    entries = []
    for path in sorted((PROJECT_ROOT / "data" / "scenarios").glob("*.json")):
        try:
            scenario = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue  # a malformed file must not take the whole index down
        if "scenario_id" not in scenario or "presented_to_user" not in scenario:
            continue  # not a scenario file (e.g. a stray cache artifact)
        if domain and scenario.get("domain") != domain:
            continue
        entries.append({
            "scenario_id": scenario["scenario_id"],
            "domain": scenario.get("domain"),
            "title": scenario.get("title"),
            "difficulty": scenario.get("difficulty"),
            "is_mock_data": _is_mock(scenario),
        })
    return entries


def _response(status: int, body) -> dict:
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def handler(event, context=None):
    """API Gateway proxy handler. GET, optional ?domain=f1|valorant|cs2."""
    params = event.get("queryStringParameters") or {}
    domain = params.get("domain")
    if domain and domain not in ("f1", "valorant", "cs2"):
        return _response(400, {"error": f"unknown domain '{domain}'"})
    return _response(200, {"scenarios": _list_scenarios(domain)})


if __name__ == "__main__":
    print(json.dumps(handler({"queryStringParameters": None}), indent=2))
