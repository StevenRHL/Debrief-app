"""Shared auth layer for Debrief — mock Cognito locally, real Cognito on deploy.

Mode selection is config, not code:
  AUTH_MODE=mock     (default when MOCK_MODE is on)  -> local fake tokens, no AWS.
  AUTH_MODE=cognito                                   -> real Cognito user pool
                                                        (debrief-user-pool) via boto3.

Both modes expose the same three functions — `sign_up`, `login`, `verify_token` —
returning the same shapes, so the handlers and the frontend never care which mode
is active. Swapping to real Cognito is: set AUTH_MODE=cognito plus
COGNITO_USER_POOL_ID / COGNITO_CLIENT_ID in the environment. No code changes.

Mock tokens are NOT security — they are deliberately transparent (base64 JSON with
an expiry) so local demos work offline and tests can assert on their contents.
The real-mode JWTs from Cognito are verified server-side per request.
"""

import base64
import hashlib
import json
import os
import time

TOKEN_TTL_SECONDS = 8 * 3600  # mock session length; Cognito manages its own


def _auth_mode() -> str:
    mode = os.environ.get("AUTH_MODE", "").strip().lower()
    if mode in ("mock", "cognito"):
        return mode
    # Default: follow the mock gate (legacy MOCK_MODE override, else the
    # per-domain default of mock) so one setting still drives auth.
    from .mock_mode import mock_mode
    return "mock" if mock_mode() else "cognito"


# --------------------------------------------------------------------------- #
# Mock mode — local fake sessions, zero AWS
# --------------------------------------------------------------------------- #
def _mock_user_id(username: str) -> str:
    # Deterministic per username so history/progress views are stable across runs.
    return "mock-" + hashlib.sha256(username.lower().encode()).hexdigest()[:12]


def _mock_token(username: str) -> str:
    payload = {
        "sub": _mock_user_id(username),
        "username": username,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "iss": "debrief-mock-auth",
    }
    return "mock." + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _mock_verify(token: str):
    if not token.startswith("mock."):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(token[len("mock."):].encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("iss") != "debrief-mock-auth" or payload.get("exp", 0) < time.time():
        return None
    return {"user_id": payload["sub"], "username": payload["username"]}


# --------------------------------------------------------------------------- #
# Real mode — Cognito user pool (debrief-user-pool). Written and correct, but
# unused while MOCK_MODE/AUTH_MODE=mock. boto3 is imported lazily so mock mode
# stays stdlib-only.
# --------------------------------------------------------------------------- #
def _cognito_client():
    import boto3  # lazy: mock mode never needs it
    return boto3.client("cognito-idp", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _cognito_sign_up(username: str, password: str):
    client = _cognito_client()
    resp = client.sign_up(
        ClientId=os.environ["COGNITO_CLIENT_ID"],
        Username=username,
        Password=password,
    )
    return {"user_id": resp["UserSub"], "username": username, "confirmed": resp["UserConfirmed"]}


def _cognito_login(username: str, password: str):
    client = _cognito_client()
    resp = client.initiate_auth(
        ClientId=os.environ["COGNITO_CLIENT_ID"],
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    auth = resp["AuthenticationResult"]
    return {
        "token": auth["IdToken"],
        "access_token": auth["AccessToken"],
        "refresh_token": auth.get("RefreshToken"),
        "expires_in": auth["ExpiresIn"],
    }


def _cognito_verify(token: str):
    # Server-side verification via Cognito itself (get_user on the access token).
    # A production hardening pass could verify the JWT signature locally against
    # the pool's JWKS instead; this keeps the scaffold dependency-light.
    client = _cognito_client()
    try:
        resp = client.get_user(AccessToken=token)
    except Exception:
        return None
    attrs = {a["Name"]: a["Value"] for a in resp.get("UserAttributes", [])}
    return {"user_id": attrs.get("sub"), "username": resp["Username"]}


# --------------------------------------------------------------------------- #
# The mode-agnostic API the handlers use
# --------------------------------------------------------------------------- #
def sign_up(username: str, password: str) -> dict:
    """Create an account. Mock mode accepts anything non-empty (no password
    store — mock login is intentionally open); Cognito mode creates a real user."""
    if not username or not password:
        raise ValueError("username and password are required")
    if _auth_mode() == "mock":
        return {"user_id": _mock_user_id(username), "username": username, "confirmed": True}
    return _cognito_sign_up(username, password)


def login(username: str, password: str) -> dict:
    """Returns {token, user_id, username, expires_in, mode}."""
    if not username or not password:
        raise ValueError("username and password are required")
    if _auth_mode() == "mock":
        return {
            "token": _mock_token(username),
            "user_id": _mock_user_id(username),
            "username": username,
            "expires_in": TOKEN_TTL_SECONDS,
            "mode": "mock",
        }
    result = _cognito_login(username, password)
    user = _cognito_verify(result["access_token"])
    return {
        "token": result["access_token"],
        "user_id": user["user_id"] if user else None,
        "username": username,
        "expires_in": result["expires_in"],
        "mode": "cognito",
    }


def verify_token(token: str):
    """Returns {user_id, username} or None. Handlers use this as the per-request
    trust boundary for anything user-scoped (history, stored attempts)."""
    if not token:
        return None
    if _auth_mode() == "mock":
        return _mock_verify(token)
    return _cognito_verify(token)


def user_from_event(event) -> dict | None:
    """Pull and verify the bearer token from an API Gateway proxy event."""
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return verify_token(auth[7:].strip())
    return None
