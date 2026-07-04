# Deploying Debrief (AWS + Vercel)

> **GATED.** Nothing in this document has been executed. Deployment happens only
> on the project owner's explicit greenlight, with real credentials supplied by
> them. Until then the app runs fully local in mock mode — see `docs/DEMO.md`.

The backend is one SAM stack (`infra/template.yaml`); the frontend is a stock
Next.js app on Vercel. There are no other moving parts.

## What the stack creates

| Resource | Name | Notes |
|---|---|---|
| HTTP API | `debrief-api` | Same routes as `scripts/local_api.py` |
| Lambda | `debrief-fetch-scenario-router` | `GET /fetch-scenario?domain=...` |
| Lambda | `debrief-list-scenarios` | `GET /list-scenarios` |
| Lambda | `debrief-grade-attempt` | `POST /grade-attempt` — the Anthropic call |
| Lambda | `debrief-auth-hook` | `/auth/signup`, `/auth/login`, `/auth/me` |
| Lambda | `debrief-fetch-history` | `GET /history` |
| DynamoDB | `debrief-scenarios` | + `domain-index` GSI (spoiler-safe projection) |
| DynamoDB | `debrief-attempts` | PK `user_id`, SK `timestamp` |
| DynamoDB | `debrief-match-cache` | TTL'd real-mode built scenarios |
| Cognito | `debrief-user-pool` + `debrief-web` client | `USER_PASSWORD_AUTH` |

The deployed stack runs with `MOCK_MODE=false` and `AUTH_MODE=cognito` — it is
the live stack by definition. Local mock mode is unaffected by any of this.

## Prerequisites

- AWS CLI + SAM CLI installed, an AWS account, credentials configured (`aws configure`).
- A real Anthropic API key (the owner supplies this — never generated or guessed).
- A Vercel account.
- Recommended before first deploy: the live grading validation run
  (`python3 scripts/stress_test_grading.py`, no mock flag) has passed its three
  checks — deploying an unvalidated rubric wastes real API spend.

## 1. Backend

```bash
cd infra
sam build
sam deploy --guided \
  --parameter-overrides \
    AnthropicApiKey=<real key> \
    HenrikdevApiKey=<optional> \
    TrackerggAppId=<optional>
```

`--guided` writes `samconfig.toml` (gitignored territory — check before committing).
Note the stack outputs: `ApiUrl`, `UserPoolId`, `UserPoolClientId`.

Production hardening to schedule after the first deploy works:
- Move `AnthropicApiKey` from a template parameter to Secrets Manager.
- Tighten the API CORS `AllowOrigins` from `*` to the Vercel domain.
- Verify Cognito JWTs locally against the pool JWKS instead of `get_user` per
  request (noted in `lambdas/shared/auth.py`).

## 2. Seed scenarios

```bash
python3 scripts/seed_dynamodb.py            # dry run — always do this first
python3 scripts/seed_dynamodb.py --execute  # writes to debrief-scenarios
```

Then swap the Lambda-side loaders to DynamoDB (the swap points are comments in
each handler: `_load_scenario`, `_list_scenarios`, `_cache_scenario`). Until
that swap lands, the deployed Lambdas serve scenarios from the files packaged
with the code (`DEBRIEF_DATA_ROOT=/var/task`), which works but means a redeploy
per new scenario.

## 3. Frontend (Vercel)

Next.js on Vercel is zero-config; the only wiring is one env var.

```bash
cd frontend
npx vercel link          # project name: debrief
npx vercel env add NEXT_PUBLIC_API_BASE production   # = the ApiUrl stack output
npx vercel deploy --prod
```

## 4. Smoke test

```bash
API=<ApiUrl>
curl "$API/list-scenarios?domain=f1"
curl "$API/fetch-scenario?domain=f1"          # must NOT contain ground_truth
curl -X POST "$API/auth/signup" -d '{"username":"you","password":"********"}'
# then login, grade one attempt with the Bearer token, and check /history
```

The spoiler-safety check matters most: no response from `/fetch-scenario` or
`/list-scenarios` may ever contain `ground_truth` or `verified_data_points`.
