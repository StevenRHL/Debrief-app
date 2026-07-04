# Debrief frontend (Phase 1, mock mode)

Single-loop teach-back UI: show a scenario → submit an explanation → see graded
feedback. Talks to the local API (`scripts/local_api.py`) which runs the
scaffolded Lambdas in **mock mode** — clickable end to end with no AWS and no
Anthropic cost.

## Run it locally

Two terminals from the project root:

```bash
# 1. Local API (API Gateway simulator) in mock mode
MOCK_MODE=true python3 scripts/local_api.py        # http://localhost:8000

# 2. Frontend
cd frontend
cp .env.local.example .env.local                   # points at localhost:8000
npm install
npm run dev                                         # http://localhost:3000
```

Open http://localhost:3000, read the Monza scenario, type ≥40 words, submit,
and you get a mock verdict rendered from the same JSON `debrief-grade-attempt`
returns.

## Going live later

Nothing in this app changes. Point the API at real grading by restarting the
backend without mock mode:

```bash
unset MOCK_MODE
export ANTHROPIC_API_KEY=sk-ant-...
python3 scripts/local_api.py
```

## Not included yet

Deployment to Vercel. This is local-only until that step is greenlit.
