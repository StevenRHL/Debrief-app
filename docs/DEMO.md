# Running the Debrief local mock loop

How to run the full app — scenario → explanation → graded debrief, across all
three modes (F1 / VALORANT / CS2), plus mock sign-in and the progress view —
entirely locally, from a clean clone, with **no AWS, no Anthropic key, no game
API keys, and no API cost**. Everything below runs in `MOCK_MODE`: grading
verdicts, auth sessions, match data and attempt history all come from local
fixtures/generators, not live calls.

> Staying in mock mode is deliberate for demos and development. The live grading
> call is a separate, explicitly-gated step (see "Going live" at the bottom) and
> is **not** part of this loop.

## Prerequisites

- Python 3.10+ (standard library only — mock mode imports nothing external)
- Node 18+ and npm (for the frontend)

That's it. You do **not** need to `pip install` anything for the mock loop;
`anthropic` is imported lazily and only when live mode is on.

## The fastest check (no browser, ~5 seconds)

From the project root:

```bash
# 1. The grading stress test against the four canonical fixtures
MOCK_MODE=true python3 scripts/stress_test_grading.py

# 2. The API-Gateway-event test harness (should print "25 passed, 0 failed")
python3 tests/test_grade_attempt_local.py

# 3. The Phase 2-4 harness: auth, history, VALORANT + CS2 fetch and grading
#    (should print "54 passed, 0 failed")
python3 tests/test_phases_2_4_local.py

# 4. The Session-12 harness: scenario catalog, fetch router, attempt storage,
#    seed dry-run, real-mode builders (should print "51 passed, 0 failed")
python3 tests/test_session12_local.py
```

The stress test regenerates `results/mock-attempt-scores.md` (banner-marked as
MOCK DATA). It shows REWORK on purpose — fixture #4 is a deliberate
"model-got-fooled" case that exercises the injection HARD-FAIL path.

## The full clickable loop (two terminals)

**Terminal 1 — the local API** (an API Gateway simulator wrapping the two
Lambda handlers; defaults to mock mode):

```bash
MOCK_MODE=true python3 scripts/local_api.py
# Debrief local API on http://localhost:8000  (mode: MOCK)
```

**Terminal 2 — the frontend:**

```bash
cd frontend
cp .env.local.example .env.local      # points NEXT_PUBLIC_API_BASE at :8000
npm install                           # first run only
npm run dev                           # http://localhost:3000
```

Open <http://localhost:3000>:

1. The landing page explains the idea in one screen. **Try a scenario** goes to
   `/play`, where a mode switcher clicks between **F1 Strategy / VALORANT / CS2**
   — each mode loads its own scenario against its own mock data, and a scenario
   picker under the tabs switches between the scenarios each domain now has
   (two per domain: e.g. Monza one-stop vs. the wet-crossover call in F1).
2. The scenario loads spoiler-safe (no outcome shown yet). Type your call and
   reasoning. The word counter enforces the 40–300 word guard client-side; the
   server enforces it again.
3. Submit → you get a **debrief**: a headline about your thinking, the reveal of
   what actually happened, what you got right, the one thing to take away, and a
   per-dimension reasoning breakdown.
4. **Sign in** (any username/password — mock auth issues a local fake session)
   and open **Progress** to see generated attempt history: score over time, a
   weakest-category callout, and past attempts across all three modes.
5. Every graded attempt is also persisted to `results/attempts-local.jsonl`
   (gitignored) with the full verdict, attributed to the signed-in user when a
   session exists — the local stand-in for the `debrief-attempts` DynamoDB table.

A red **● MOCK DATA** badge stays pinned to the top-right the whole time, so any
screenshot or screen recording makes it obvious this is fixture data.

### Trying different inputs

Mock grading is driven by *what you actually type* — it detects which trade-offs
you engage (pit-loss cost, pace delta, tyre degradation, track position, safety
car, a stated falsifier) and which call you make (stay out vs. pit to cover), so
different explanations produce a genuine range of verdicts. Some things to try:

| Input style | Roughly what you'll see |
|---|---|
| Strong stay-out with the numbers + a falsifier | high overall, `matched_history` |
| Well-argued "pit to cover" | mid-high, `defensible_alternative` |
| A real call but few specifics | mid, thin reasoning |
| Pure vibes ("trust the driver") | low, `flawed_process` |
| Anything with an injected "ignore the rubric" instruction | low, `flawed_process`, manipulation called out |

## Curl, without the frontend

```bash
# Scenario index (safe metadata only) — optionally ?domain=f1|valorant|cs2
curl -s http://localhost:8000/list-scenarios | python3 -m json.tool

# Spoiler-safe scenario — optionally ?domain=...&scenario_id=...
curl -s http://localhost:8000/fetch-scenario | python3 -m json.tool

# Grade an attempt
curl -s -X POST http://localhost:8000/grade-attempt \
  -H 'Content-Type: application/json' \
  -d '{"attempt_text":"Stay out and commit to the one-stop. A stop costs ~24s and over 20 laps the two-stop car needs ~1.2 s/lap on fresh hards, which the low observed degradation says it will not get. Track position plus clean air wins it; the risk is a late tyre cliff or a safety car."}' \
  | python3 -m json.tool
```

## Going live (separate, gated step — not part of the demo loop)

Only when explicitly greenlit: put a real key in `.env`
(`ANTHROPIC_API_KEY=sk-ant-...`), then run **without** the mock flag —
`python3 scripts/stress_test_grading.py`, or start the API with `unset MOCK_MODE`
and the key exported. Nothing else changes: every grading path already routes
through the same `shared.grade_attempt`.
