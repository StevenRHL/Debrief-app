"""Per-domain mock-mode gating — one source of truth for every Lambda/script.

Previously MOCK_MODE was a single global switch. It is now split per domain so
one game can go live while the others stay on fixtures:

    MOCK_MODE_F1        (default "true")
    MOCK_MODE_VALORANT  (default "true")
    MOCK_MODE_CS2       (default "true")

MOCK_MODE is kept as a LEGACY GLOBAL OVERRIDE: if it is set to a non-empty value
it wins for every domain, so existing workflows (local dev exporting MOCK_MODE,
the Vercel `MOCK_MODE=true` env var) keep working with zero changes. Leave it
unset to use the per-domain flags.

Defaults keep the whole app on fixtures (every flag defaults to mock=true), so
nothing goes live by accident.
"""

import os

_TRUTHY = ("1", "true", "yes", "on")
DOMAINS = ("f1", "valorant", "cs2")


def _truthy(val: str) -> bool:
    return val.strip().lower() in _TRUTHY


def _legacy_override():
    """Return the bool the legacy MOCK_MODE forces, or None if it isn't set."""
    raw = os.environ.get("MOCK_MODE")
    if raw is None or raw.strip() == "":
        return None
    return _truthy(raw)


def mock_mode(domain: str | None = None) -> bool:
    """Whether `domain` should use fixtures (True) instead of live calls (False).

    - If MOCK_MODE is explicitly set, it overrides every domain (legacy behavior).
    - Otherwise use MOCK_MODE_<DOMAIN> (default true).
    - With no domain and no global override, default to mock (safe default) — used
      by domain-agnostic paths (auth, history) that aren't tied to one game.
    """
    override = _legacy_override()
    if override is not None:
        return override
    if domain:
        key = f"MOCK_MODE_{domain.strip().upper()}"
        return _truthy(os.environ.get(key, "true"))
    return True


def domain_modes() -> dict:
    """{domain: is_mock} for all three domains — for badges / status endpoints."""
    return {d: mock_mode(d) for d in DOMAINS}
