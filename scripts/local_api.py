"""Local API Gateway simulator for the Debrief Lambdas.

Runs the two scaffolded handlers behind a plain stdlib HTTP server so the
Next.js frontend can hit a real endpoint with no AWS and no API cost. Defaults
to MOCK_MODE so nothing calls Anthropic.

    MOCK_MODE=true python3 scripts/local_api.py        # default port 8000

Routes (all mirror API Gateway proxy events):
    GET  /fetch-scenario[?scenario_id=...&domain=f1|valorant|cs2]
                                        -> the matching debrief-fetch-* Lambda
    GET  /list-scenarios[?domain=...]   -> debrief-list-scenarios (picker index)
    POST /grade-attempt   {scenario_id?, attempt_text}  -> debrief-grade-attempt
    POST /auth/signup     {username, password}          -> debrief-auth-hook
    POST /auth/login      {username, password}          -> debrief-auth-hook
    GET  /auth/me         Authorization: Bearer …       -> debrief-auth-hook
    GET  /history         Authorization: Bearer …       -> debrief-fetch-history

Mock gating is per-domain: MOCK_MODE_F1 / MOCK_MODE_VALORANT / MOCK_MODE_CS2
(each default true), with MOCK_MODE as a legacy global override. To take one
domain live, set e.g. MOCK_MODE_F1=false and export that domain's credentials
(see .env.example at the project root).
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lambdas"))

# NB: we deliberately do NOT force MOCK_MODE=true here — that would act as the
# legacy global override and make the per-domain MOCK_MODE_<DOMAIN> flags moot.
# Every domain defaults to mock anyway (see shared/mock_mode.py), so a plain run
# is still fully mock; set MOCK_MODE_F1=false etc. to take one domain live.

import debrief_auth_hook  # noqa: E402
import debrief_fetch_history  # noqa: E402
import debrief_fetch_scenario_router  # noqa: E402
import debrief_grade_attempt  # noqa: E402
import debrief_list_scenarios  # noqa: E402
from shared.mock_mode import domain_modes  # noqa: E402

PORT = int(os.environ.get("DEBRIEF_LOCAL_PORT", "8000"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, lambda_result):
        self.send_response(lambda_result["statusCode"])
        for k, v in lambda_result.get("headers", {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(lambda_result["body"].encode())

    def _cors_preflight(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        self._cors_preflight()

    def _headers_dict(self):
        return {k: v for k, v in self.headers.items()}

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if parsed.path == "/fetch-scenario":
            # The router owns domain dispatch — same code path as the deployed
            # /fetch-scenario route in infra/template.yaml.
            event = {"httpMethod": "GET", "queryStringParameters": qs or None}
            self._send(debrief_fetch_scenario_router.handler(event))
        elif parsed.path == "/list-scenarios":
            event = {"httpMethod": "GET", "queryStringParameters": qs or None}
            self._send(debrief_list_scenarios.handler(event))
        elif parsed.path == "/mock-status":
            # Per-domain mock/live status, so the frontend badge can say which
            # domain is live if they ever differ. Progressive enhancement — the
            # UI falls back to a generic badge if this route is unavailable.
            self._send({"statusCode": 200,
                        "headers": {"Content-Type": "application/json",
                                    "Access-Control-Allow-Origin": "*"},
                        "body": json.dumps({"domains": domain_modes()})})
        elif parsed.path == "/auth/me":
            event = {"httpMethod": "GET", "path": parsed.path, "headers": self._headers_dict()}
            self._send(debrief_auth_hook.handler(event))
        elif parsed.path == "/history":
            event = {"httpMethod": "GET", "path": parsed.path, "headers": self._headers_dict(),
                     "queryStringParameters": qs or None}
            self._send(debrief_fetch_history.handler(event))
        else:
            self._send({"statusCode": 404, "headers": {"Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"}, "body": json.dumps({"error": "not found"})})

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode() if length else "{}"
        if parsed.path == "/grade-attempt":
            # Headers included so a signed-in user's attempts are attributed to
            # them in storage; anonymous grading still works without them.
            event = {"httpMethod": "POST", "body": raw, "headers": self._headers_dict()}
            self._send(debrief_grade_attempt.handler(event))
        elif parsed.path in ("/auth/login", "/auth/signup"):
            event = {"httpMethod": "POST", "path": parsed.path, "body": raw,
                     "headers": self._headers_dict()}
            self._send(debrief_auth_hook.handler(event))
        else:
            self._send({"statusCode": 404, "headers": {"Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"}, "body": json.dumps({"error": "not found"})})

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write("[local_api] " + (fmt % args) + "\n")


def main():
    modes = domain_modes()  # {domain: is_mock}
    summary = ", ".join(f"{d}={'MOCK' if m else 'LIVE'}" for d, m in modes.items())
    print(f"Debrief local API on http://localhost:{PORT}  (per-domain: {summary})")
    print("  GET  /fetch-scenario")
    print("  GET  /list-scenarios")
    print("  GET  /mock-status")
    print("  POST /grade-attempt")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
