# Debrief

Debrief is a learning app built around one idea: the best way to know if you actually understand something is to explain your reasoning out loud.

You're shown a real decision moment — starting with F1 race strategy, plus VALORANT and CS2 — and you explain, in plain English, what you'd do and *why*. An AI then grades your **reasoning** against what actually happened and against sound decision-making. It's the anti-flashcard: it rewards process over recognition, and a well-argued "wrong" answer beats a lucky guess with no logic behind it.

> **Status:** scaffold running entirely in **mock mode**. The whole app is runnable end-to-end with zero API cost and zero network calls. Every live path (Anthropic, AWS, game-data APIs) is written but gated behind config — going live is a matter of adding credentials, not writing code.

---

## How it works

1. **A scenario is presented** — the situation only, with no spoilers about the outcome (e.g. *Monza 2024, lap 33: Leclerc P2 on 17-lap-old hards, McLaren just committed to a two-stop. Stay out or pit?*).
2. **You explain your call** in 40–300 words: the decision and the reasoning behind it.
3. **You get a debrief** — the outcome is revealed, and your reasoning is scored across four weighted dimensions:

   | Dimension | Weight |
   |---|---|
   | Reasoning quality | 40 |
   | Decision | 20 |
   | Risk awareness | 20 |
   | Calibration | 20 |

   Anti-outcome-bias rules are built into the grader so a sound alternative call doesn't get zeroed just because it isn't what happened.

---

## Running it locally (mock mode — no keys, no network)

Mock mode uses hand-written fixtures and a deterministic, feature-driven synthesizer, so the grade responds to what you actually type. It needs **zero** pip installs (the `anthropic`/`boto3` libraries are imported lazily in the live paths only).

**Stress-test the grader** against the built-in fixtures:
```bash
MOCK_MODE=true python3 scripts/stress_test_grading.py
```

**Run the tests:**
```bash
python3 tests/test_grade_attempt_local.py      # 25/25
python3 tests/test_phases_2_4_local.py         # 54/54
python3 tests/test_session12_local.py          # 51/51 — catalog, storage, builders
```

**Run the full clickable loop** (two terminals):
```bash
# Terminal 1 — local API (stands in for API Gateway)
MOCK_MODE=true python3 scripts/local_api.py    # :8000

# Terminal 2 — frontend
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                                    # :3000
```
Then open http://localhost:3000. Every page carries a `● MOCK DATA` badge so demos are never mistaken for real grading.

See [`docs/DEMO.md`](docs/DEMO.md) for a clean-clone walkthrough and input examples.

---

## Frontend

Next.js 14 (app router, TypeScript):

- `/` — landing page
- `/play` — the debrief loop, with an **F1 / VALORANT / CS2** mode switcher and a scenario picker per domain
- `/progress` — score-over-time, weakest-category callout, per-dimension breakdown
- `/login` — mock sign-in

---

## Project layout

```
data/        Curated scenarios + raw game-data pulls (spoiler-safe split)
prompts/     Grading system prompts (per domain) + structured-output schema
lambdas/     AWS Lambda handlers + shared grading core (shared/grading.py)
scripts/     Stress-test harness, local API server, DynamoDB seed (dry-run)
tests/       API-event tests (mock mode)
frontend/    Next.js app
infra/       AWS SAM template (scaffold — nothing deployed)
docs/        Roadmap + demo guide + deploy runbook
```

The single grading entry point is `grade_attempt()` in `lambdas/shared/grading.py`, used identically by the test harness and the Lambda. Mock gating is **per domain** (`shared/mock_mode.py`): `MOCK_MODE_F1`, `MOCK_MODE_VALORANT`, `MOCK_MODE_CS2` each default to `true`, so one game can go live while the others stay on fixtures. `MOCK_MODE` remains a legacy global override — if set, it wins for every domain (keeps `MOCK_MODE=true` on Vercel and old local workflows working). The in-app badge shows which domains are live vs mock if they ever differ.

---

## Going live (not enabled here)

Every real-mode path is written and flips on by config alone:

| Feature | To enable |
|---|---|
| Claude grading (F1) | `MOCK_MODE_F1=false` + real `ANTHROPIC_API_KEY`. Model is `CLAUDE_MODEL` (default `claude-opus-4-8`). |
| Auth | `AUTH_MODE=cognito` + Cognito pool/client IDs |
| VALORANT data | `MOCK_MODE_VALORANT=false` + `HENRIKDEV_API_KEY` |
| CS2 data | `MOCK_MODE_CS2=false` + `TRACKERGG_APP_ID` |

(Or set the legacy `MOCK_MODE=false` to flip every domain live at once.)

Every variable the finished app uses is documented (with empty placeholders) in [`.env.example`](.env.example). Deployment (AWS SAM + Vercel) is scaffolded in [`infra/template.yaml`](infra/template.yaml) and documented in [`docs/DEPLOY.md`](docs/DEPLOY.md) — nothing is deployed; it is gated on an explicit greenlight.

> **No secrets are committed to this repo.** The real `.env` is gitignored; only the placeholder `.env.example` is tracked. Never commit real keys.

---

## Roadmap

- **Phase 1** — F1 (OpenF1 data) ✅ scaffolded
- **Phase 2** — accounts + attempt history + progress view ✅ scaffolded
- **Phase 3** — VALORANT ✅ scaffolded
- **Phase 4** — CS2 ✅ scaffolded

Full plan and naming conventions live in `docs/`.
