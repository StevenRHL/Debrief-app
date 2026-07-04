"""debrief-auth-hook — sign-up / login / session check.

SCAFFOLD / NOT DEPLOYED. Thin handler over shared/auth.py, which does mock
sessions locally (AUTH_MODE=mock, the default while MOCK_MODE is on) and real
Cognito (debrief-user-pool) when AUTH_MODE=cognito. Same request/response
shapes in both modes, so going live is config only.

Routes (path-based, mirroring API Gateway proxy routing):
    POST /auth/signup  {username, password}
    POST /auth/login   {username, password}     -> {token, user_id, ...}
    GET  /auth/me      Authorization: Bearer …  -> {user_id, username}
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make `shared` importable

from shared import auth  # noqa: E402

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _response(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def handler(event, context=None):
    path = (event.get("path") or "").rstrip("/")
    method = event.get("httpMethod", "GET").upper()

    if path.endswith("/auth/me") and method == "GET":
        user = auth.user_from_event(event)
        if not user:
            return _response(401, {"error": "invalid or expired session"})
        return _response(200, user)

    try:
        body = event.get("body") or "{}"
        if isinstance(body, str):
            body = json.loads(body)
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid JSON body"})

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    try:
        if path.endswith("/auth/signup") and method == "POST":
            return _response(200, auth.sign_up(username, password))
        if path.endswith("/auth/login") and method == "POST":
            return _response(200, auth.login(username, password))
    except ValueError as e:
        return _response(400, {"error": str(e)})

    return _response(404, {"error": "not found"})


if __name__ == "__main__":
    import os
    os.environ.setdefault("MOCK_MODE", "true")
    ev = {"httpMethod": "POST", "path": "/auth/login",
          "body": json.dumps({"username": "demo", "password": "x"})}
    out = handler(ev)
    print(json.dumps(out, indent=2))
    token = json.loads(out["body"])["token"]
    me = handler({"httpMethod": "GET", "path": "/auth/me",
                  "headers": {"Authorization": f"Bearer {token}"}})
    print(json.dumps(me, indent=2))
