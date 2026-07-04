"""Fetch + normalize the Monza track layout and lap-33 car positions from OpenF1.

Produces a build/dev-time FIXTURE the frontend renders — the browser never calls
OpenF1 live (same data-fetching philosophy as MOCK_MODE: fetch once, cache, serve
fixtures). Outputs go to:

    data/track_layouts/monza-2024.json           (canonical)
    frontend/lib/fixtures/monza-track.json        (frontend-consumable copy)

Data source: OpenF1 /location endpoint (x/y car telemetry), session_key 9590
(2024 Italian GP). The track OUTLINE is one driver's x/y over a full lap; the CAR
markers are every target driver's x/y at the scenario's decision moment (lap 33).
Coordinates are normalized into a 0..1 range (aspect-ratio preserved) for SVG.

Usage:
    python3 scripts/fetch_track_layout.py            # fetch real telemetry
    python3 scripts/fetch_track_layout.py --schematic # write labeled placeholder

If the live fetch fails (no network / OpenF1 auth / SSL), the script writes a
clearly-labeled SCHEMATIC placeholder (is_real_telemetry: false) so the component
still renders, and exits non-zero so CI notices. Re-run with network access to
replace it with real telemetry.
"""

import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_CANONICAL = ROOT / "data" / "track_layouts" / "monza-2024.json"
OUT_FRONTEND = ROOT / "frontend" / "lib" / "fixtures" / "monza-track.json"

SESSION_KEY = 9590
DECISION_LAP = 33
RACE_START = datetime(2024, 9, 1, 13, 3, 34)  # lap 1 start (UTC), from laps_lec.json
AVG_LAP_SECONDS = 84  # ~84s/lap at Monza; used only to locate the lap-33 window

OPENF1 = "https://api.openf1.org/v1"

# Target drivers at the decision moment, in the running order the scenario cares
# about. Numbers + team colours are real (data/raw/monza-2024/drivers.json).
TARGET_DRIVERS = [
    {"num": 81, "code": "PIA", "name": "Piastri", "team": "McLaren", "color": "FF8000"},
    {"num": 16, "code": "LEC", "name": "Leclerc", "team": "Ferrari", "color": "E8002D"},
    {"num": 4, "code": "NOR", "name": "Norris", "team": "McLaren", "color": "FF8000"},
    {"num": 55, "code": "SAI", "name": "Sainz", "team": "Ferrari", "color": "E8002D"},
]


def _ctx() -> ssl.SSLContext:
    # OpenF1 sometimes trips macOS' missing-root-cert setup; fall back to an
    # unverified context for this read-only public fixture fetch.
    try:
        import certifi  # noqa: F401
        return ssl.create_default_context()
    except Exception:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def _get(path: str, params: dict) -> list:
    qs = urllib.parse.urlencode(params, safe="<>")
    url = f"{OPENF1}/{path}?{qs}"
    with urllib.request.urlopen(url, timeout=30, context=_ctx()) as r:
        return json.load(r)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _lap_window(lap: int):
    start = RACE_START + timedelta(seconds=(lap - 1) * AVG_LAP_SECONDS)
    return start, start + timedelta(seconds=AVG_LAP_SECONDS + 6)


def _normalizer(points):
    """Return a fn mapping (x,y) -> (0..1, 0..1), aspect ratio preserved, y up."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    span = max(maxx - minx, maxy - miny) or 1.0
    padx = (span - (maxx - minx)) / 2
    pady = (span - (maxy - miny)) / 2

    def norm(x, y):
        nx = (x - minx + padx) / span
        ny = (y - miny + pady) / span
        return round(nx, 4), round(1 - ny, 4)  # 1-ny: SVG y grows downward

    return norm


def fetch_real() -> dict:
    """Pull the outline (one driver, one lap) + car snapshot from OpenF1."""
    start, end = _lap_window(DECISION_LAP)
    # Outline: Leclerc's x/y across the lap-33 window.
    outline_rows = _get("location", {
        "session_key": SESSION_KEY, "driver_number": 16,
        "date>": _iso(start), "date<": _iso(end),
    })
    raw = [(r["x"], r["y"]) for r in outline_rows if r.get("x") is not None]
    if len(raw) < 50:
        raise RuntimeError(f"outline too sparse ({len(raw)} points) — bad window?")

    # Car snapshot: each target driver's position at a single instant mid-lap.
    snap_at = start + timedelta(seconds=AVG_LAP_SECONDS // 2)
    cars_raw = {}
    for d in TARGET_DRIVERS:
        rows = _get("location", {
            "session_key": SESSION_KEY, "driver_number": d["num"],
            "date>": _iso(snap_at), "date<": _iso(snap_at + timedelta(seconds=3)),
        })
        pt = next(((r["x"], r["y"]) for r in rows if r.get("x") is not None), None)
        if pt:
            cars_raw[d["num"]] = pt

    norm = _normalizer(raw + list(cars_raw.values()))
    outline = [list(norm(x, y)) for x, y in raw]
    cars = []
    for i, d in enumerate(TARGET_DRIVERS, start=1):
        if d["num"] in cars_raw:
            nx, ny = norm(*cars_raw[d["num"]])
            cars.append({**{k: d[k] for k in ("code", "name", "team", "color")},
                         "x": nx, "y": ny, "position": i})

    return {
        "circuit": "Autodromo Nazionale Monza",
        "session_key": SESSION_KEY,
        "decision_lap": DECISION_LAP,
        "is_real_telemetry": True,
        "source": "OpenF1 /location, session_key 9590 (2024 Italian GP)",
        "outline": outline,
        "cars": cars,
    }


# --------------------------------------------------------------------------- #
# Schematic fallback — clearly labeled placeholder, NOT telemetry.
# The circuit shape is a recognizable Monza schematic (public track geometry);
# driver identities + running order are real, x/y along the track are approximate.
# --------------------------------------------------------------------------- #
_MONZA_SCHEMATIC = [
    [0.20, 0.94], [0.42, 0.95], [0.62, 0.95], [0.70, 0.93], [0.71, 0.88],
    [0.66, 0.85], [0.63, 0.82], [0.66, 0.78], [0.72, 0.74], [0.80, 0.66],
    [0.86, 0.57], [0.90, 0.47], [0.88, 0.42], [0.83, 0.42], [0.80, 0.46],
    [0.80, 0.52], [0.83, 0.55], [0.88, 0.55], [0.93, 0.51], [0.95, 0.44],
    [0.93, 0.36], [0.86, 0.33], [0.74, 0.33], [0.58, 0.34], [0.46, 0.35],
    [0.40, 0.32], [0.42, 0.27], [0.48, 0.26], [0.51, 0.30], [0.49, 0.35],
    [0.42, 0.38], [0.30, 0.40], [0.18, 0.43], [0.10, 0.50], [0.08, 0.60],
    [0.09, 0.72], [0.12, 0.84], [0.16, 0.91], [0.20, 0.94],
]


def _point_on_outline(frac: float):
    n = len(_MONZA_SCHEMATIC) - 1
    idx = int(frac * n) % n
    return _MONZA_SCHEMATIC[idx]


def build_schematic() -> dict:
    cars = []
    # Spread the field along the front portion of the lap for a legible snapshot.
    for i, d in enumerate(TARGET_DRIVERS, start=1):
        x, y = _point_on_outline(0.02 + i * 0.05)
        cars.append({**{k: d[k] for k in ("code", "name", "team", "color")},
                     "x": x, "y": y, "position": i})
    return {
        "circuit": "Autodromo Nazionale Monza",
        "session_key": SESSION_KEY,
        "decision_lap": DECISION_LAP,
        "is_real_telemetry": False,
        "source": ("SCHEMATIC PLACEHOLDER — circuit shape is an approximate Monza "
                   "schematic and car x/y are illustrative. Driver identities and "
                   "running order are real. Run scripts/fetch_track_layout.py with "
                   "OpenF1 network access to replace with real /location telemetry."),
        "outline": _MONZA_SCHEMATIC,
        "cars": cars,
    }


def _write(payload: dict):
    for path in (OUT_CANONICAL, OUT_FRONTEND):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
        print(f"  wrote {path.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schematic", action="store_true",
                    help="skip the live fetch and write the labeled placeholder")
    args = ap.parse_args()

    if not args.schematic:
        try:
            print("Fetching real OpenF1 /location telemetry (session 9590, lap 33)...")
            payload = fetch_real()
            print(f"  outline points: {len(payload['outline'])}, cars: {len(payload['cars'])}")
            _write(payload)
            print("Done — real telemetry fixture written.")
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"  live fetch failed ({type(e).__name__}: {e})", file=sys.stderr)
            print("  falling back to the labeled SCHEMATIC placeholder.", file=sys.stderr)

    _write(build_schematic())
    print("Wrote SCHEMATIC placeholder (is_real_telemetry: false). "
          "Re-run with network access for real telemetry.")
    return 0 if args.schematic else 1


if __name__ == "__main__":
    sys.exit(main())
