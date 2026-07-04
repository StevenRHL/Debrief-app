"""debrief-fetch-scenario-router — one /fetch-scenario route for all domains.

SCAFFOLD / NOT DEPLOYED. The frontend calls GET /fetch-scenario?domain=... ; this
router dispatches to the matching per-domain fetch Lambda module so the deployed
API (infra/template.yaml) and the local simulator (scripts/local_api.py) expose
the identical route shape. In AWS all four fetch functions ship in the same
package, so importing the siblings directly costs nothing.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import debrief_fetch_cs2_stats  # noqa: E402
import debrief_fetch_f1_scenario  # noqa: E402
import debrief_fetch_valorant_match  # noqa: E402

FETCH_BY_DOMAIN = {
    "f1": debrief_fetch_f1_scenario,
    "valorant": debrief_fetch_valorant_match,
    "cs2": debrief_fetch_cs2_stats,
}

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def handler(event, context=None):
    params = dict(event.get("queryStringParameters") or {})
    domain = params.pop("domain", "f1")
    target = FETCH_BY_DOMAIN.get(domain)
    if not target:
        return {"statusCode": 400, "headers": CORS_HEADERS,
                "body": json.dumps({"error": f"unknown domain '{domain}'"})}
    return target.handler({**event, "queryStringParameters": params or None}, context)
