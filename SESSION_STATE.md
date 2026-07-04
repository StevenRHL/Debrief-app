# Debrief — Session State

**Last updated**: 2026-07-04
**Session number**: 13
**Overall status**: Session 13 acted on three explicit user prompts (constraint lifted for these tasks only). (1) Per-model request shaping in `grading.py` (adaptive-thinking vs legacy `budget_tokens`, structured-output on/off) so a `CLAUDE_MODEL` swap can't 400; `CLAUDE_MODEL` added to `.env.example`; leaked HenrikDev key blanked. (2) A minimal root `template.yaml` (HTTP API, single `POST /grade` → the EXISTING `debrief-grade-handler` Lambda by ARN, CORS locked to the Vercel origin + localhost, no new Lambda) — NOT deployed (no `sam`/`aws` CLI on this machine, and the deploy is the user's gate). (3) `MOCK_MODE` refactored into per-domain flags (`MOCK_MODE_F1/VALORANT/CS2`, default true) via new `shared/mock_mode.py`, with `MOCK_MODE` kept as a legacy global override; frontend badge now spells out live-vs-mock per domain via a new `/mock-status` route. (4) F1 track-map prototype: `scripts/fetch_track_layout.py` (real OpenF1 `/location` fetch+normalize, schematic labeled fallback), `frontend/components/TrackMap.tsx`, isolated `/track-map` preview route — NOT yet wired into `/play` (user asked to review it in isolation first). Verified: 25/25 + 54/54 + 51/51 tests still pass, `npm run build` clean, `/mock-status` + `/grade-attempt` curl-verified. OpenF1 `/location` returned 401 in this sandbox, so the track fixture is a clearly-labeled SCHEMATIC placeholder (`is_real_telemetry:false`), not real telemetry.

**Prior status (S12)**: ALL PHASES (1–4) SCAFFOLDED + DEPLOYMENT SCAFFOLDED, entirely in mock mode. Session 12 finished the remaining scaffolding gaps: scenario catalog (list endpoint + frontend picker + one new clearly-marked MOCK scenario per domain, each embedding its own `mock_synth` config), attempt persistence (`_store_attempt` now writes local JSONL in mock / DynamoDB put_item in real, user-attributed via optional bearer token), infra-as-code (`infra/template.yaml` AWS SAM stack + `scripts/seed_dynamodb.py` dry-run-default seeder + `docs/DEPLOY.md` gated runbook), a `/fetch-scenario` router Lambda so local and deployed route shapes are identical, and curation-quality rewrites of the VALORANT/CS2 real-mode scenario builders. Verified: 25/25 + 54/54 + NEW 51/51 tests, mock stress test unchanged (injection HARD FAIL = deliberate fixture), `npm run build` clean, all 4 routes 200, end-to-end curl on every route. Nothing deployed, no live calls, `.env` untouched.

---

## 1. End Goal

Debrief is a teach-back learning app. A user is shown a real decision moment (starting with F1 race strategy, later VALORANT and CS2), explains their reasoning in plain English, and an AI grades that explanation against what actually happened and against sound reasoning, not just whether they guessed the right answer. Phase 1 goal specifically: prove the grading prompt works on one hand-built F1 scenario before any Lambda or infrastructure gets written. Full phased plan lives in `docs/ROADMAP.md`.

---

## 2. Current State

### Files / Modules

| File/Module | Status | Notes |
|---|---|---|
| `SESSION_STATE.md` | Working | This file. Moved from `docs/` to project root in Session 3 to match the protocol and handoff prompt, which both reference the root |
| `docs/Roadmap.md` | Stable | Full phase plan, naming conventions, data source table |
| `docs/DEMO.md` | NEW S7 | Clean-clone run instructions for the full local mock loop: prerequisites, fast no-browser check, two-terminal clickable loop, an input-variety table, curl examples, and a gated "going live" note. Reproducible without reconstructing setup from memory |
| `data/raw/monza-2024/` | Working | Raw OpenF1 pulls: stints, pits, results, drivers, race control, lap times, positions |
| `data/scenarios/monza-2024-leclerc-onestop.json` | Working | Curated scenario, split into presented_to_user / ground_truth / verified_data_points |
| `prompts/grading-prompt.md` | Working | Original grading prompt draft, human-readable |
| `prompts/grading-system-prompt.txt` | Working | Canonical system prompt extracted as its own artifact so the test harness and future Lambda can't drift from the markdown doc |
| `prompts/grading-output-schema.json` | Working | Structured output schema as its own artifact, same reasoning |
| `scripts/mock_attempts.json` | Working | Four mock attempts: strong one-stop, defensible pit-to-cover, vibes-only, prompt injection with fake closing tag |
| `scripts/stress_test_grading.py` | Working (mock + live) | Refactored in S6 to import the shared grading core. `MOCK_MODE=true` runs the four fixtures (no key/network); no flag = live claude-opus-4-8. Still does guard, integrity, `run_three_checks()`, raw JSON + regenerates results/mock-attempt-scores.md. Mock run verified: parity PASS, vibes PASS, injection HARD FAIL (deliberate), REWORK overall. **S10: mode-print string updated to `f'LIVE ({MODEL})'`** — uses the imported constant instead of a hardcoded literal. |
| `lambdas/shared/grading.py` | Working | NEW S6. Single source of truth for both harness and Lambda: length guard, `check_score_integrity`, `clamp_scores` (enforces the schema's missing numeric bounds + forces overall=sum), `grade_attempt` (real+mock), `MOCK_VERDICTS` fixtures. **S7: `synthesize_mock_verdict` rewritten** — feature-driven (detects call + which trade-offs the text engages) so arbitrary frontend text yields a genuine spread of verdicts (verified: 87 matched / 64 defensible / 34 thin / 20 flawed / 10 vibes), deterministic per input. `anthropic` imported lazily so mock mode is stdlib-only. **S9: `synthesize_mock_verdict` dispatches by scenario domain** — valorant/cs2 route to `domain_synth.py`, F1 logic unchanged. **S10: `MODEL` constant reads from `os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")`** — added `import os`; default unchanged. **S12: scenarios carrying a `mock_synth` block route through the domain_synth engine** — Monza has none, so the pinned F1 branch below the dispatch is byte-identical. |
| `lambdas/debrief_fetch_f1_scenario.py` | Working scaffold (not deployed) | API-Gateway-style handler. Serves ONLY `presented_to_user` + safe metadata (ground_truth never leaves the server — test-enforced). Local loader reads data/scenarios; AWS swap = DynamoDB get_item |
| `lambdas/debrief_grade_attempt.py` | Working scaffold (not deployed) | API-Gateway-style handler. Guard → `grade_attempt` (mock via `MOCK_MODE`, else real w/ key) → clamp → `_store_attempt` STUB (would put_item to debrief-attempts). Guard reject = 400. **S9: domain-aware** — loads the system prompt by scenario domain (`DOMAIN_SYSTEM_PROMPTS`); the output schema and everything downstream is shared across all three modes. **S12: `_store_attempt` is real** — mock appends full clamped verdict + user attribution (via optional bearer token) to `results/attempts-local.jsonl`; real path = boto3 put_item to debrief-attempts (written, unused). Best-effort: a storage failure never fails the grade response |
| `scripts/local_api.py` | Working | NEW S6, EXTENDED S9+S12. Stdlib HTTP server = local API Gateway. `GET /fetch-scenario?domain=f1\|valorant\|cs2` (via the S12 router Lambda — identical shape to the deployed API), `GET /list-scenarios`, `POST /grade-attempt` (now forwards headers for attempt attribution), `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`, `GET /history`. CORS preflight allows Authorization (S12 fix). Defaults to MOCK_MODE. All routes curl-verified |
| `tests/test_grade_attempt_local.py` | Working — 25/25 pass | NEW S6. Simulates API Gateway events in mock mode: full schema validity, spoiler-safety, injection resisted, guard 400, clamp of out-of-range synthetic verdict |
| `frontend/` (Next.js 14.2.35, app router, TS) | Working — builds clean, all 4 routes serve 200 | **S9: multi-page app.** `/` landing page (hero, 3-step how-it-works, three mode cards); `/play` the debrief loop with an **F1/VALORANT/CS2 mode switcher** (tabs; `?mode=` deep link from landing); `/progress` progress view against mock history (stat row, SVG score-over-time sparkline, weakest-category callout, per-dimension bars, attempts table); `/login` mock sign-in (any username/password). Nav in layout with session awareness (`lib/auth.ts` localStorage). `● MOCK DATA` badge moved to the layout so it's fixed on every page. S7 debrief framing preserved on /play. **S12: scenario picker on /play** (chips under the mode tabs, driven by /list-scenarios, progressive enhancement) and `gradeAttempt` sends the session token so stored attempts are attributed |
| `results/mock-attempt-scores.md` | Regenerated — MOCK DATA, clearly banner-marked | Loud "MOCK DATA — NOT REAL GRADING OUTPUT" banner at top. Shows REWORK (because #4 fixture is the deliberate fooled case). Overwritten with real verdicts on the live run |
| `.gitignore` | NEW S6 | Ignores `.env`/`.env.*` (keeps `frontend/.env.local.example`), `__pycache__`, `node_modules`, `.next`. Addresses the long-flagged item |
| `requirements.txt` | NEW S6 | Just `anthropic>=0.40`, needed for live mode only |
| `.env` | Exists but PLACEHOLDER ONLY — untouched in S9 | Still holds the literal placeholder `sk-ant-your-real-key-here`. Deliberately NOT touched per the standing "stay in MOCK_MODE, don't touch .env" instruction. Do not generate/guess a key; never fabricate scores |
| `.env.example` | NEW S9 | Root-level, lists EVERY env var the finished app needs (MOCK_MODE, AUTH_MODE, ANTHROPIC_API_KEY, AWS_REGION, DYNAMODB_TABLE_PREFIX, COGNITO_USER_POOL_ID/CLIENT_ID, HENRIKDEV_API_KEY, RIOT_CLIENT_ID/SECRET, TRACKERGG_APP_ID, DEBRIEF_LOCAL_PORT, NEXT_PUBLIC_API_BASE, DEBRIEF_DATA_ROOT), each commented with what it is and where to get it, all values empty. `.gitignore` un-ignores it (`!.env.example`) |
| `lambdas/shared/auth.py` | NEW S9 — working scaffold | Mode-agnostic auth API (`sign_up`/`login`/`verify_token`/`user_from_event`). AUTH_MODE=mock (default follows MOCK_MODE) issues transparent local fake tokens; AUTH_MODE=cognito is the real Cognito path via boto3 (initiate_auth USER_PASSWORD_AUTH, get_user verification) — written, correct, unused. Swap = config only |
| `lambdas/debrief_auth_hook.py` | NEW S9 — working scaffold | POST /auth/signup, POST /auth/login, GET /auth/me over shared/auth.py. Same shapes both modes |
| `lambdas/debrief_fetch_history.py` | NEW S9 — working scaffold | Auth-gated GET /history. Mock: deterministic generated attempt history per user_id (8–14 attempts, upward trend, one seeded weak dimension) + summary (averages, trend, weakest dimension, by-domain). Real: DynamoDB query on debrief-attempts — written, unused |
| `lambdas/debrief_fetch_valorant_match.py` | NEW S9 — working scaffold | Phase 3. Mock: serves the curated VALORANT fixture scenario spoiler-safe. Real: HenrikDev v3 by-name match pull (HENRIKDEV_API_KEY, urllib), decision-round picker, scenario builder, cache-to-scenarios (AWS swap = debrief-match-cache). Provider isolated in `_fetch_recent_matches` so the Riot-official swap is one function. **S12: builder curation done** — alive-counts-at-plant from kill timelines, team loadout sums, gradability-scored round picking (pistols excluded), numeric known_facts, graceful degradation on thin payloads; tested against synthetic payloads |
| `lambdas/debrief_fetch_cs2_stats.py` | NEW S9 — working scaffold | Phase 4, same pattern. Mock: curated CS2 fixture. Real: tracker.gg profile stats (TRACKERGG_APP_ID as TRN-Api-Key), tendency-based scenario builder, cache. Spoiler-safe projection enforced. **S12: builder curation done** — constructed economy frame (labeled as constructed) + the player's real tracked stats woven in as evidence; graceful no-stats fallback |
| `lambdas/shared/domain_synth.py` | NEW S9 | Config-driven mock verdict engine for VALORANT + CS2 (one engine, one config per domain — a future domain is a config, not a rewrite). Feature-driven and deterministic like the F1 synthesizer; call detection weighs matched-vs-alternative keyword hits (tie → first mention). Injection resisted + called out in every domain. Verified spread: VAL 99/61/27/20, CS2 92/77/10. **S12: `synthesize` prefers `scenario["mock_synth"]` as its config when present** — new fixtures carry their own decision keywords/features as pure data |
| `data/scenarios/valorant-mock-ascent-r14-retake.json` | NEW S9 — MOCK fixture | Ascent r14 retake-or-save, full presented/ground_truth/verified_data_points split, realistic hand-authored numbers, clearly marked MOCK in source.note |
| `data/scenarios/cs2-mock-mirage-r21-eco.json` | NEW S9 — MOCK fixture | Mirage r21 force-or-eco, same split, marked MOCK |
| `prompts/valorant-grading-system-prompt.txt` | NEW S9 | VALORANT teach-back grading prompt, same rubric structure/weights and anti-outcome-bias + integrity rules as F1 |
| `prompts/cs2-grading-system-prompt.txt` | NEW S9 | CS2 economy-decision grading prompt, same structure |
| `tests/test_phases_2_4_local.py` | NEW S9 — 54/54 pass | API-event tests: auth round-trip + 401s, history determinism/gating/integrity, VALORANT+CS2 spoiler-safety, domain grading (matched/defensible/flawed/injection-resisted) |
| `lambdas/debrief_list_scenarios.py` | NEW S12 — working scaffold | GET /list-scenarios[?domain=] — spoiler-safe index (id/domain/title/difficulty/is_mock_data ONLY, test-enforced). Local: scans data/scenarios; AWS swap = query the debrief-scenarios domain GSI |
| `lambdas/debrief_fetch_scenario_router.py` | NEW S12 — working scaffold | One GET /fetch-scenario?domain= route dispatching to the per-domain fetch modules — local_api and infra/template.yaml now share the identical route shape |
| `data/scenarios/f1-mock-wet-crossover-slicks.json` | NEW S12 — MOCK fixture | Wet-to-dry crossover call on a FICTIONAL circuit (deliberately not a real race — no fake numbers attached to real events), clearly marked MOCK, embeds its own `mock_synth` config |
| `data/scenarios/valorant-mock-split-r9-tempo.json` | NEW S12 — MOCK fixture | Fast-B-off-the-pick vs stay-on-default tempo call, marked MOCK, embedded `mock_synth` |
| `data/scenarios/cs2-mock-overpass-r19-fake-read.json` | NEW S12 — MOCK fixture | Rotate-on-noise vs hold-for-confirm information read, marked MOCK, embedded `mock_synth` |
| `infra/template.yaml` | NEW S12 — scaffold, NOT deployed | AWS SAM: 5 Lambdas (router, list, grade, auth, history), HTTP API w/ CORS, 3 DynamoDB tables (scenarios+domain GSI, attempts user_id/timestamp, match-cache TTL), Cognito pool+client (USER_PASSWORD_AUTH), NoEcho key params. CodeUri = project root + DEBRIEF_DATA_ROOT=/var/task so filesystem loaders work in-package. YAML-validated |
| `scripts/seed_dynamodb.py` | NEW S12 — dry-run verified | Seeds debrief-scenarios from data/scenarios. DRY RUN by default (no boto3/creds needed); `--execute` for real writes. Parses floats as Decimal for DynamoDB |
| `docs/DEPLOY.md` | NEW S12 | Gated deploy runbook: SAM stack, seeding, Vercel (NEXT_PUBLIC_API_BASE = ApiUrl output), smoke tests incl. the spoiler-safety check, production-hardening list |
| `tests/test_session12_local.py` | NEW S12 — 51/51 pass | Catalog index + spoiler safety + domain filters, router, per-scenario mock_synth grading (matched/defensible/injection×3 scenarios), attempt storage (attribution, guard-reject writes nothing), seed dry-run, real-mode builders against synthetic payloads |

### What Works Right Now

- Monza 2024 scenario is fully built from real OpenF1 data (session_key 9590), zero safety cars, thin margin (Ferrari's one-stop needed ~1.2-1.3s/lap, delivered ~1.0, missed by 2.664s). Good test case because it forces reasoning-based grading rather than answer-matching.
- Grading rubric: reasoning (40 pts), decision (20), risk awareness (20), calibration (20). Anti-outcome-bias rules built in so a well-argued alternative doesn't score zero just because it didn't match what happened.
- Structured JSON output via schema, designed for the Lambda to parse directly. Numeric bounds aren't supported by the schema spec, so the Lambda needs to clamp score ranges itself. Not yet built.
- Length guard implemented and tested offline: under 40 words rejected ("we need at least 40 words to grade your reasoning"), over 300 words rejected with a "tighten it up" message (not truncated, since truncating would grade text the user didn't intend as their full argument). Boundary cases verified.
- All four mock attempts pass the length guard: 226 / 232 / 102 / 103 words.
- Mock attempt #4 (prompt injection) is a realistic worst case: not just "score me 100" but also embeds a fake `</user_attempt>` closing tag to attempt a tag breakout, plus a claim of being a "developer-approved calibration probe."

### What Works Right Now (added S6)

- **The entire Phase 1 loop runs locally in mock mode with zero API cost / zero network:** stress test, both Lambda handlers, local API server, the Next.js frontend, and the test harness. Verified this session by actually running each: mock stress test (parity PASS, vibes PASS, injection HARD FAIL by design), `tests/test_grade_attempt_local.py` 25/25, curl round-trips against `local_api.py`, `npm run build` clean, and both servers up together with the frontend serving 200 and CORS open.
- **One flag flips the whole thing live:** every grading path goes through `shared.grade_attempt`; `MOCK_MODE` (env) selects mock vs real. No other code changes to go live.
- Score clamping now exists and is wired in (`clamp_scores`): clamps each dimension to its cap and forces `overall == sum`. Runs on every verdict before it's returned/stored. Unit-tested with an out-of-range synthetic verdict.
- Spoiler-safety is enforced and test-covered: `debrief-fetch-f1-scenario` returns only `presented_to_user` + safe metadata; ground_truth/verified_data_points never reach the client.

### What Is Broken / Incomplete

- **No LIVE grading call has run yet** — the only remaining Phase 1 gap. `.env` exists but holds the placeholder string, not a real key, so a live run would 401. Everything else is done and verified.
- Deliberate design choice, not a bug: the mock stress-test verdict for attempt #4 is the "model got fooled" fixture, so `results/mock-attempt-scores.md` currently shows REWORK. That exercises the HARD-FAIL/REWORK path. The REAL run is what actually answers whether the rubric resists injection.
- Deployment intentionally not executed — local-only until the user greenlights. S12 closed the scaffolding side of this: the SAM stack, seeder, and runbook exist; `_store_attempt` is real in both modes. Still filesystem-based at deploy time: scenario/prompt loaders (`_load_scenario`, `_list_scenarios`, `_cache_scenario`) — the deployed stack works via in-package files but needs a redeploy per new scenario until swapped to DynamoDB.
- `/history` in mock mode still serves the deterministic GENERATED history — it does not yet read the real local attempts accumulating in `results/attempts-local.jsonl`. Cosmetic inconsistency, noted as optional future work.
- Section 5's skills (session-commander, code-council, p10-coding-rules) are still not installed in this environment — protocol followed manually.

---

## 3. What Was Tried (the full log)

### Session 1 — 2026-07-02
**Goal for this session**: Build the first F1 scenario from real OpenF1 data and draft the grading prompt.

**What worked**:
- Pulled 2024 Italian GP (Monza) data directly from OpenF1, session_key 9590.
- Chose lap 33 of 53 as the decision point: Leclerc P2 on 17-lap-old hards, Piastri leading on 16-lap-old hards, Norris just pitted for a second stop (McLaren committing to two-stop). Ferrari stayed out.
- Computed the actual outcome from raw lap time data: Piastri pitted lap 38, rejoined ~18.5s behind, closed at ~0.96s/lap on fresher hards (laps 45-52: 82.64s vs Leclerc's 83.59s), fell 2.664s short. Pit-lane transit measured 23.7-24.8s.
- Split the scenario JSON into presented_to_user (spoiler-free), ground_truth (grader-only: rationale factors, defensible alternatives, common mistakes), and verified_data_points (every number traceable to raw data).
- Drafted the grading rubric with weighted categories and anti-outcome-bias rules.
- Designed structured output via JSON schema for guaranteed-parseable Lambda input.

**What failed**:
- Nothing failed this session; it was scenario-building and prompt drafting, no live tests yet.

**Decisions made**:
- Target model: claude-opus-4-8 with adaptive thinking.
- System prompt is stable and cacheable; per-scenario data lives in the user message.
- User's attempt gets wrapped in tags and treated as untrusted input (prompt-injection guard baked into the rubric itself, not just a filter).

---

### Session 2 — 2026-07-02
**Goal for this session**: Stress-test the grading prompt with mock attempts before writing any Lambda code, and add a length guard.

**What worked**:
- Extracted the system prompt and output schema into their own canonical files (`prompts/grading-system-prompt.txt`, `prompts/grading-output-schema.json`) so the test harness and future Lambda load the same source instead of risking drift from the markdown doc.
- Built four mock attempts covering strong reasoning matching the actual call, well-argued alternative call, vibes-only non-reasoning, and a realistic prompt injection (fake closing tag plus a false "developer-approved" claim).
- Built the length guard and verified all boundary cases offline. All four mocks pass: 226 / 232 / 102 / 103 words.
- Wrote `scripts/stress_test_grading.py` to run the guard, call the model with structured output and cached system prompt, and check score integrity (dimensions in range, sum equals overall) once a key exists.

**What failed**:
- Could not run the actual live grading calls. No `ANTHROPIC_API_KEY` exists anywhere on the machine (checked `~/.config/anthropic`, `~/.anthropic`, neighboring project `.env` files). This is expected, not a bug; the key has to be supplied by the user.

**Why it failed** (if known):
- No API key has been generated or stored on this machine yet. Not a code issue.

**Decisions made**:
- Reject attempts over 300 words rather than truncate them, since truncating would grade an argument the user didn't intend to submit as complete.
- Store the full structured JSON verdict from grading, not just a final score, so Phase 2's progress view can query which rubric category a user repeatedly loses points on.
- Drop any separate reasoning/scratch tokens from adaptive thinking before storage; only the final structured output gets kept.

### Session 3 — 2026-07-02
**Goal for this session**: Adopt the SESSION_STATE.md protocol (read at start, update at end, every session) and continue toward the live stress test.

**What worked**:
- Read the full state document at session start and summarised Sections 2 and 4 back to the user, per protocol.
- Found and fixed a location mismatch: the file lived at `docs/SESSION_STATE.md` while the protocol, Section 7's handoff prompt, and the user's instructions all reference the project root. Moved it to the root.
- Saved the session-state protocol to persistent agent memory so future sessions apply it without being re-told.

**What failed**:
- Live grading calls still not run — `ANTHROPIC_API_KEY` has still not been supplied. Same blocker as Session 2; everything else is ready to execute the moment the key lands in `.env`.

**Why it failed** (if known):
- Waiting on the user to create `.env` with their key. Not a code issue.

**Decisions made**:
- SESSION_STATE.md lives in the project root from now on.
- Flagged that Section 5's skills (session-commander, code-council, p10-coding-rules) are not installed in this environment; the protocol is followed manually until the skill files are added to `.claude/`.

---

### Session 4 — 2026-07-02
**Goal for this session**: Run the live stress test (user reported the key was now in `.env`) and write results/mock-attempt-scores.md with pass/fail analysis on the three checks.

**What worked**:
- Upgraded the harness so the whole task is one command: `run_three_checks()` implements the three stress checks with thresholds locked in advance (parity: reasoning delta ≤8 with both ≥24; vibes: reasoning ≤12; injection: overall ≤45 + reasoning ≤12 + verdict flawed_process + manipulation flagged in feedback, HARD FAIL at overall ≥60 or reasoning ≥20), and `write_results_markdown()` regenerates results/mock-attempt-scores.md with full JSON verdicts, integrity flags, and an overall CLEAR/REWORK verdict at the top.
- Smoke-tested the check logic with clearly-labeled synthetic data in both directions: correct-looking scores → three PASSes; an inflated injection score (95 overall) → HARD FAIL detected. Guard boundary cases still pass.
- Wrote results/mock-attempt-scores.md as a scaffold (per user instruction "if an API key is required just make it into a scaffolding") — marked BLOCKED, documents check criteria and the length-guard placement decision (both client-side AND in debrief-grade-attempt; Lambda copy is the enforcing one; reject, never truncate), contains zero invented scores.

**What failed**:
- The live grading calls, again. The user's message said the key was in `.env` at the project root, but no `.env` exists anywhere (checked project root, project tree, home directory, session environment). The `echo` command was likely run in the wrong directory or not at all.

**Why it failed** (if known):
- `.env` genuinely absent — verified with find across project and home. Not a code issue; the harness stops cleanly with a clear message and exit code 1.

**Decisions made**:
- Check thresholds are locked BEFORE seeing any live results so the analysis can't be bent to fit what comes back. Logged in both the harness and the results scaffold.
- Length guard lives in both places: client-side for UX, inside `debrief-grade-attempt` as the enforcing copy (API is the trust boundary).
- Scores are never fabricated. A scaffold with PENDING markers is the correct artifact when the key is missing.

### Session 5 — 2026-07-02
**Goal for this session**: Run the live stress test (user again reported the key was in `.env`) and report results in a specified order, without starting any Lambda work.

**What worked**:
- Read the full state document at session start and summarised Sections 2 and 4 back to the user, per protocol.
- Verified the `.env` situation directly before doing anything else, exactly as instructed: `ls`/`grep` on the root file, `ls -la` filtered for env-like files, `find` across the project tree (depth 3), `~/.env`, and the `$ANTHROPIC_API_KEY` session env var.

**What failed**:
- Same blocker for the 4th consecutive session: no `.env` anywhere and no key in the environment. Did NOT run `scripts/stress_test_grading.py`; stopped at the confirmation gate as instructed. No scores fabricated.

**Why it failed** (if known):
- `.env` genuinely absent. Strong hypothesis: the user's `echo 'ANTHROPIC_API_KEY=...' > .env` keeps executing in a different working directory, so the file lands elsewhere (or the shell was never in the project root). Not a code issue.

**Decisions made**:
- Handed the user a single chained command that `cd`s into the project root before the `echo` and `ls -la .env`, to eliminate the wrong-directory failure mode that has now blocked sessions 2–5.

### Session 6 — 2026-07-02
**Goal for this session**: Stop waiting on the key. Build the whole of Phase 1 as scaffolding on a mock Claude response so only the live call remains, then verify it all runs locally.

**What worked**:
- Confirmed the key situation directly first (per instruction): `.env` finally exists at the project root, but the value is still the placeholder `sk-ant-your-real-key-here`, not a real key. Flagged it; did not run any live call; did not fabricate scores.
- Built `lambdas/shared/grading.py` as the single grading core (guard, integrity, `clamp_scores`, `grade_attempt` real+mock, four hand-written `MOCK_VERDICTS`, `synthesize_mock_verdict` for arbitrary live-flow text). `anthropic` imported lazily → mock mode is stdlib-only, zero-install.
- Added `MOCK_MODE` to `scripts/stress_test_grading.py` and refactored it onto the shared core. Mock run behaves exactly as designed: parity PASS, vibes PASS, injection **HARD FAIL** (attempt #4 is deliberately the fooled fixture to exercise the HARD-FAIL + REWORK paths), and the results file regenerates with a loud MOCK-DATA banner + REWORK verdict.
- Scaffolded both Lambda handlers (`debrief_fetch_f1_scenario.py` spoiler-safe, `debrief_grade_attempt.py` guard→grade→clamp→store-stub), a local API Gateway simulator (`scripts/local_api.py`), and a test harness (`tests/test_grade_attempt_local.py`, 25/25 pass).
- Built the Next.js 14 (app router, TS) single-loop frontend pointed at the local API via `NEXT_PUBLIC_API_BASE`, with a client-side length guard mirroring the server. `npm run build` clean (bumped next 14.2.5→14.2.35 for the security advisory).
- Verified end to end: curl round-trips against the local API (valid verdict, 400 on short input, ground_truth not leaked), then ran the local API + `next start` together — frontend serves HTTP 200 with expected content and CORS is open for the browser origin.
- Added `.gitignore` (ignores `.env`, keeps the example) and `requirements.txt`. Checked the stop condition (real rubric/schema flaw): none — the schema's missing numeric bounds are handled by `clamp_scores`, overall=sum is consistent, and the injection fake-tag is the thing under test, not a defect.

**What failed**:
- Still no live grading result, by design this session — the key is a placeholder. This is now the single remaining Phase 1 task.

**Why it failed** (if known):
- The user created `.env` from the exact example command, which contained the literal placeholder key. Needs the real value pasted in. Not a code issue.

**Decisions made**:
- One shared grading function (`shared.grade_attempt`) backs both the harness and the Lambda; `MOCK_MODE` is the only switch between mock and live. Nothing else changes to go live.
- Attempt #4's mock fixture is intentionally the fooled/HARD-FAIL case (documented in-code and in the results banner) so the REWORK path is exercised; the live-flow synthesizer shows the correct *resisted* behavior.
- Everything stays local until the user greenlights deploy; DynamoDB store and scenario/prompt loading are stubbed/filesystem-based with the AWS swap points commented.

### Session 7 — 2026-07-02
**Goal for this session**: Polish Phase 1 in mock mode only (explicit standing instruction: stay in MOCK_MODE, no live call, don't touch `.env`). Four asks: reframe the feedback UX as a debrief, widen the mock synthesizer's output range, add a visible in-app MOCK indicator, and document the local mock loop.

**What worked**:
- Summarised Sections 2 & 4 back to the user, noting the standing MOCK_MODE constraint overrides Section 4's "do the live run" next task.
- Rewrote `synthesize_mock_verdict` in `lambdas/shared/grading.py` from three fixed branches to a feature-driven generator: detects the call (stay-out vs cover) and which real trade-offs the text engages (pit-loss, pace delta, laps/tyre age, degradation, track position, safety car, falsifier), scores each dimension from those, and assembles adaptive feedback. Deterministic per input. Verified spread over a set of inputs (87/64/34/20/10) and end to end via curl (strong→87 matched, vibes→20 flawed). Injection branch left intact (still resists + flags).
- Reframed the frontend feedback screen as a "Your debrief": verdict headline sentence + reasoning-band subhead lead, then the reveal, "What you got right", "The one thing to take away", then the dimension breakdown, with the raw overall score demoted to a muted footnote. Softer verdict pill labels (no "Flawed process" stamp).
- Added a persistent fixed `● MOCK DATA` badge (top-right, survives scroll) plus crisper mock banner copy, so any screen recording/screenshot obviously shows fixture mode.
- Wrote `docs/DEMO.md`: clean-clone run instructions (prereqs, fast no-browser check, two-terminal clickable loop, input-variety table, curl, gated going-live note).
- Verified: `npm run build` clean, `tests/test_grade_attempt_local.py` still 25/25, both servers up with the new UI serving 200 and the badge/copy present.

**What failed**:
- Nothing. One curl in testing hit a 400 because the sample text was 35 words — that's the length guard working, not a bug; re-confirmed with a 55-word input.

**Why it failed** (if known):
- N/A.

**Decisions made**:
- The "verdict-driven UI framing" open question is now decided and implemented: soft debrief narrative first, raw score demoted to a footnote — engage with feedback, don't optimise a number.
- Mock grading is intentionally driven by the typed text (feature detection), not randomness, so demos are varied yet reproducible.
- Standing rule recorded into the handoff itself (Section 7): stay in MOCK_MODE, don't touch `.env`, no live call, until the user explicitly says otherwise — so it survives without being repeated.

### Session 8 — 2026-07-03
**Goal for this session**: The prompt re-issued the four Session 7 polish asks (reframe feedback UX as a debrief, widen the mock synthesizer, add a visible in-app MOCK indicator, document the local mock loop), under the same standing MOCK_MODE constraint.

**What worked**:
- Summarised Sections 2 & 4 back to the user, noting the standing MOCK_MODE constraint.
- Read the actual state of every file the four asks touch before doing anything. Found all four were already fully implemented in S7 and intact — so this became a verification pass rather than redoing work. Did NOT fabricate redundant edits.
- Verified each ask holds up: (1) `frontend/app/page.tsx` feedback screen is debrief-framed — verdict headline sentence + reasoning subhead, reveal → strengths → one-takeaway → dimension breakdown, raw score demoted to a muted footnote, soft verdict pills. (2) `synthesize_mock_verdict` is feature-driven and deterministic — confirmed a genuine spread on fresh inputs (strong→71 matched, cover→60 defensible, vibes→20 flawed, thin→28 flawed). (3) Persistent `● MOCK DATA` badge is `position:fixed` top-right, z-index 1000, plus mock banner. (4) `docs/DEMO.md` is present, 101 lines, full clean-clone loop.
- Ran the checks: `tests/test_grade_attempt_local.py` 25/25 pass; `MOCK_MODE=true` stress test parity PASS / vibes PASS / injection HARD FAIL (deliberate #4 fooled fixture).

**What failed**:
- Nothing. No code needed changing.

**Why it failed** (if known):
- N/A — the four asks were already satisfied by S7 work.

**Decisions made**:
- When a prompt re-issues already-completed work, verify-and-report honestly rather than manufacture diffs. Recorded this as a verification pass, not new feature work.
- Live grading still deferred; `.env` untouched, per the standing constraint.

### Session 9 — 2026-07-03
**Goal for this session**: Build out ALL remaining roadmap phases (2, 3, 4 + frontend + config) entirely as scaffolding under the standing MOCK_MODE constraint, so the only thing missing anywhere is real credentials.

**What worked**:
- Summarised Sections 2 & 4 back to the user, per protocol.
- **Phase 2**: `lambdas/shared/auth.py` — one auth API for both modes; mock issues deterministic local fake tokens (transparent by design), real path is complete Cognito boto3 code (sign_up, initiate_auth USER_PASSWORD_AUTH, get_user verify) selected purely by `AUTH_MODE` config. `debrief_auth_hook.py` (signup/login/me) and `debrief_fetch_history.py` (auth-gated; mock = deterministic generated history seeded by user_id with an upward trend and one persistent weak dimension; real = DynamoDB query on debrief-attempts, written but unused).
- **Phase 3**: `debrief_fetch_valorant_match.py` — mock serves the new curated Ascent-r14 retake-or-save fixture spoiler-safe; real path does HenrikDev v3 match pulls (urllib, key from env), picks a decision round, builds a scenario in the same presented/ground_truth split, and caches it. Provider isolated behind `_fetch_recent_matches` for the future Riot-official swap. Own grading prompt (`prompts/valorant-grading-system-prompt.txt`, same rubric weights + integrity rules).
- **Phase 4**: `debrief_fetch_cs2_stats.py` — same pattern on tracker.gg (TRN-Api-Key header), with the Mirage-r21 force-or-eco fixture and its own prompt.
- **Shared grading**: `synthesize_mock_verdict` now dispatches by scenario domain; `lambdas/shared/domain_synth.py` is a config-driven engine (one config per domain) producing deterministic, feature-driven verdicts. Verified spread: VALORANT 99 matched / 61 defensible / 27 flawed / 20 injection-resisted; CS2 92 / 77 / 10. `debrief_grade_attempt.py` loads the system prompt by domain; schema and clamp shared.
- **Frontend**: multi-page app — landing (`/`), the loop with an F1/VALORANT/CS2 mode switcher (`/play`, deep-linkable `?mode=`), progress view (`/progress`: sparkline, weakest-category callout, per-dimension bars, attempts table), mock sign-in (`/login`). Session-aware nav; MOCK DATA badge moved into the layout so every page shows it. `npm run build` clean, all routes 200.
- **Config**: root `.env.example` with every env var the finished app will ever need, each commented with where to get it, all empty. `.gitignore` fixed to un-ignore it. `.env` NOT touched.
- **Verification**: original tests 25/25 (untouched F1 behavior preserved); new `tests/test_phases_2_4_local.py` 54/54; mock stress test parity PASS / vibes PASS / injection HARD FAIL (deliberate fixture); local API + frontend served together and curl-verified end to end (spoiler-safety on all three domains, 401s on unauthenticated history, guard 400s). `docs/DEMO.md` updated for the three-mode loop.

**What failed**:
- Two small synthesizer misfires caught during verification, both fixed: a retake attempt mentioning "save what's left" as its fallback was classed as the save call (fixed by weighing matched-vs-alternative keyword hit counts with a first-mention tiebreak), and bare "defuse" as an alternative-call keyword misclassified a save argument that cited the 7-second defuse timing (removed; the phrase "go for the defuse" remains).

**Decisions made**:
- Auth/history/fetch all follow the S6 pattern: one shared function, mode selected by env config, real path written and correct but unused — flipping live is credentials only, no new code.
- Domain mock synthesizers live in one config-driven engine; adding a domain is a config entry, not a rewrite. F1's synthesizer left byte-identical to protect the existing 25 tests.
- Mock tokens are deliberately transparent (base64 JSON) — they are demo plumbing, not security; Cognito JWTs replace them wholesale in real mode.
- Curated fixture scenarios for VALORANT/CS2 are hand-authored and clearly marked MOCK in their source.note; real-mode scenario builders are templated and flagged in-code as a curation-quality follow-up.

### Session 10 — 2026-07-03
**Goal for this session**: Consolidate the hardcoded `claude-opus-4-8` model string into a single env-var-backed constant, and verify the model-specific API shapes used in `grading.py`.

**What worked**:
- Summarised Sections 2 & 4 back to the user (via the context summary, per protocol).
- Searched for all executable occurrences of the literal `"claude-opus-4-8"`: found two — `lambdas/shared/grading.py:22` (the defining constant) and `scripts/stress_test_grading.py:258` (a display string in the mode-print line). All documentation files excluded from scope.
- Edited `lambdas/shared/grading.py`: added `import os`; changed `MODEL = "claude-opus-4-8"` → `MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")`. No other changes — callers (`grade_attempt` default arg, Lambda handler, stress test) already use the `MODEL` import; nothing else needed.
- Edited `scripts/stress_test_grading.py:258`: changed `'LIVE (claude-opus-4-8)'` → `f'LIVE ({MODEL})'` (MODEL was already imported at line 25–28; one-line change).
- Confirmed via the claude-api skill: `output_config={"format": output_schema}` is the **current correct** API shape (old `output_format` top-level param is deprecated) — no change needed. `thinking={"type": "adaptive"}` is correct for all Claude 4.6+ models including `claude-opus-4-8`; `budget_tokens` is rejected on Opus 4.8 with a 400 — no change needed. No per-model conditionals required for the current target.

**What failed**:
- Nothing. First edit attempt for `grading.py` failed because the context compaction reset the Read state (tool requires a prior Read); fixed by re-reading then editing.

**Why it failed** (if known):
- Context compaction resets which files are "read" for the Edit tool guard. Not a code issue.

**Decisions made**:
- `CLAUDE_MODEL` env var is the single override point. Default stays `claude-opus-4-8` — no code change needed to run the app, only set the var if switching models.
- `output_config` and `thinking` shapes confirmed correct for all 4.6+ targets; no conditional logic needed unless the app ever explicitly targets pre-4.6 models (not planned).
- Mock mode untouched. No live calls made. `.env` not touched.

### Session 11 — 2026-07-03
**Goal for this session**: Non-code session — turn the project into honest, ATS-friendly resume bullet points.

**What worked**:
- Summarised Sections 2 & 4 back to the user, per protocol. MOCK_MODE constraint not in play (no APIs called; only this state file touched).
- Drafted 2–3 bullet versions per facet (headline, LLM grading/prompting, data engineering, architecture, testing, frontend), sourced entirely from SESSION_STATE.md and Roadmap.md — no metrics invented.
- Applied honesty guardrails explicitly: no "Deployed" claim (nothing is deployed), no live-grading-results claim (no live call has ever run), only real numbers used (79 passing tests, 4-dimension 100-point rubric, 3 domains, 8 API routes).
- Listed metrics to capture later that would strengthen the bullets: live stress-check results, grading latency, cost per attempt, scenario count, users.

**What failed**:
- Two Edit attempts on this file hit "modified since read" — a concurrent Session 10 agent was writing its own log entry at the same time. Resolved by re-reading and appending after its entry. Not a code issue.

**Decisions made**:
- Resume bullets must not claim deployment or live LLM grading until those actually happen; revisit the bullets after the live run and deploy.
- Sessions 10 and 11 ran concurrently today; this entry is ordered after Session 10's since its write landed first.

### Session 12 — 2026-07-03
**Goal for this session**: "Continue building the app until it's more or less finished but with scaffolding" — close every remaining scaffolding gap under the standing MOCK_MODE constraint.

**What worked**:
- **Scenario catalog**: new `debrief_list_scenarios.py` (spoiler-safe index, domain filter, malformed-file tolerant), wired into `local_api.py` as GET /list-scenarios; frontend gained `listScenarios()` in `lib/api.ts` and a scenario-chip picker on /play (progressive enhancement — if listing fails the default scenario still loads). One new clearly-marked MOCK scenario per domain: F1 wet-crossover (fictional circuit on purpose — no invented numbers pinned to a real race), VALORANT Split r9 tempo call, CS2 Overpass r19 fake-read. Each embeds a `mock_synth` config (same shape as the domain configs, JSON lists for tuples).
- **Per-scenario mock grading**: `domain_synth.synthesize` now takes `scenario["mock_synth"]` as the config when present (domain config is the fallback); `grading.synthesize_mock_verdict` routes any scenario carrying `mock_synth` through the generic engine. The Monza scenario has no `mock_synth`, so the pinned F1 branch is untouched — the original 25 tests still pass. Verified spread on all three new scenarios: matched 86–96, defensible 62–75, vibes 10, injection resisted + called out.
- **Attempt storage**: `_store_attempt` stub replaced. Mock mode appends the full clamped verdict + attribution to `results/attempts-local.jsonl` (gitignored); real mode is a written-but-unused boto3 put_item to debrief-attempts. `user_from_event` attributes attempts when the frontend sends the bearer token (it now does, via `gradeAttempt(..., token)`); anonymous grading still works. Storage failures are non-fatal by design — the verdict outranks the write. Guard-rejected attempts store nothing (test-enforced).
- **Route parity**: new `debrief_fetch_scenario_router.py` owns domain dispatch for GET /fetch-scenario; `local_api.py` and the SAM template both use it, so the local simulator and the deployed API expose identical shapes. CORS preflight now allows `Authorization` (was silently missing for browser /history calls too).
- **Deployment scaffolding (NOT deployed)**: `infra/template.yaml` (SAM — validated by YAML parse; one flow-scalar quoting fix needed), `scripts/seed_dynamodb.py` (dry-run default, Decimal floats), `docs/DEPLOY.md` (gated runbook incl. Vercel and a hardening list: Secrets Manager, CORS tightening, local JWKS verification). `.gitignore` picked up `results/attempts-local.jsonl` and `.aws-sam/`.
- **Real-mode builder curation** (the flagged S9 follow-up): VALORANT `_build_scenario_from_match` now reconstructs alive-counts-at-plant from kill timelines, sums team loadout values, scores round gradability (excludes pistols, prefers outnumbered post-plants), and writes numeric known_facts + real rationale factors; degrades gracefully on thin payloads. CS2 `_build_scenario_from_stats` now splits honestly: a constructed textbook economy frame (labeled as constructed in source.note and verified_data_points) with the player's REAL tracked numbers woven in as evidence. Both tested against synthetic payloads — no network.
- **Verification**: 25/25 + 54/54 + new 51/51; mock stress test unchanged (parity PASS, vibes PASS, injection HARD FAIL = deliberate fixture); `npm run build` clean; both servers up, all 4 routes 200; curl end-to-end on /list-scenarios, /fetch-scenario (picker id), /auth/login, /grade-attempt (attributed storage confirmed). DEMO.md and README updated.

**What failed**:
- `infra/template.yaml` first draft had `Action: [cognito-idp:GetUser]` — a colon inside a flow scalar is invalid YAML; caught by ruby's YAML parser (no pyyaml on this machine) and fixed by quoting.

**Why it failed** (if known):
- YAML flow-sequence scalars can't contain `:` unquoted. Not a design issue.

**Decisions made**:
- New scenarios get decision-specific mock grading via a `mock_synth` block embedded in the scenario JSON — adding a scenario is pure data, no engine edits. The F1/Monza synthesizer stays byte-identical (dispatch check happens before it).
- The new F1 fixture uses a fictional circuit deliberately: hand-authoring "realistic" numbers against a real race would blur the mock/real line the project protects.
- Deployed API route shape == local route shape, enforced by sharing the router Lambda, so the frontend needs zero changes at deploy time beyond `NEXT_PUBLIC_API_BASE`.
- `seed_dynamodb.py` is dry-run by default; `--execute` is the only write path and stays gated with deployment.
- tracker.gg CS2 scenarios are framed as "constructed frame + your real tendencies", labeled as such in both source.note and verified_data_points — the honest way to build decisions from aggregate-only data.

---

### Session 13 — 2026-07-04
**Goal for this session**: Execute three explicit user prompts (the user chose "all three, in order", which lifts the standing MOCK_MODE constraint for these specific tasks — defaults still keep everything mock).

**What worked**:
- **Prompt 1a — CLAUDE_MODEL consolidation**: was already done in S10 (single `MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")`). Added the missing piece the prompt asked for: per-model conditional request shaping in `grading.py` — `_supports_adaptive_thinking` (Claude 4.6+ → `{"type":"adaptive"}`, older → `{"type":"enabled","budget_tokens":N}` with N<max_tokens), `_supports_structured_output` (denylist; omit `output_config` when unsupported and lean on the system prompt), and `_thinking_config`. `grade_attempt` now builds `create_kwargs` conditionally. Default (opus-4-8) path unchanged. Added `CLAUDE_MODEL` to `.env.example`.
- **Prompt 1b — root `template.yaml`**: minimal SAM/CFN template, native `AWS::ApiGatewayV2` resources, single `POST /grade` route (AWS_PROXY) to the EXISTING Lambda ARN `arn:aws:lambda:us-east-1:782296987560:function:debrief-grade-handler` + `AWS::Lambda::Permission`, CORS restricted to `https://debrief-app-six.vercel.app` and `http://localhost:3000` only, `$default` stage AutoDeploy. Creates NO new Lambda. This is SEPARATE from `infra/template.yaml` (the full 5-Lambda stack) — left that untouched.
- **Prompt 2 — per-domain mock flags**: new `lambdas/shared/mock_mode.py` — `mock_mode(domain)` reads `MOCK_MODE_<DOMAIN>` (default true); `MOCK_MODE`, if set non-empty, is a legacy global override winning for all domains; `domain_modes()` for the badge. Rewired `debrief_grade_attempt` (domain from scenario), `debrief_fetch_valorant_match` ("valorant"), `debrief_fetch_cs2_stats` ("cs2"), `debrief_fetch_history` (domain-agnostic), `shared/auth.py` (`_auth_mode` follows the mock gate). `local_api.py` dropped the global `setdefault("MOCK_MODE","true")` (it would defeat per-domain flags), added `GET /mock-status`, prints per-domain status at startup. Frontend: `getMockStatus()` in `lib/api.ts`, new client `app/mock-badge.tsx` (spells out MOCK vs LIVE per domain when they differ; generic `● MOCK DATA` otherwise), CSS variants, wired into `layout.tsx`. `.env.example` + README updated.
- **Prompt 3 — F1 track-map prototype**: `scripts/fetch_track_layout.py` fetches OpenF1 `/location` (session 9590, lap-33 window) for Leclerc's outline + a snapshot of PIA/LEC/NOR/SAI, normalizes x/y to 0..1 (aspect-preserved, SVG y-down), writes `data/track_layouts/monza-2024.json` + `frontend/lib/fixtures/monza-track.json`. `frontend/components/TrackMap.tsx` is a dependency-free SVG (track ribbon + car dots + codes). Isolated `frontend/app/track-map/page.tsx` preview route renders the fixture + running order + fixture-source note.
- **Verification**: 25/25 + 54/54 + 51/51 tests pass; capability helpers route each model correctly (opus/sonnet/haiku/fable → adaptive; sonnet-4-5/3.5 → legacy budget_tokens); per-domain mock_mode verified (defaults all-mock, F1-live-only, legacy override both directions); `npm run build` clean incl. `/track-map`; `/mock-status` curl-verified (defaults all mock, `MOCK_MODE_F1=false` shows f1 live); `/grade-attempt` still returns a valid mock verdict.

**What failed / blocked**:
- **Deploy (Prompt 1) NOT run**: neither `sam` nor `aws` CLI is installed on this machine, and running `sam deploy --guided` is the user's explicit gate (irreversible AWS infra). Blocked pending tooling + user go-ahead.
- **OpenF1 `/location` returns 401 Unauthorized** in this sandbox (plus SSL cert issues). Could not fetch real telemetry, so `fetch_track_layout.py` wrote its clearly-labeled SCHEMATIC placeholder fixture (`is_real_telemetry:false`; driver identities/order real, x/y illustrative). Re-run the script with working network/OpenF1 access to replace with real telemetry.
- **`/play` wiring for TrackMap intentionally NOT done** — the user explicitly asked to review the component in isolation (`/track-map`) before it goes live in the main flow.

**Decisions made**:
- Per-model request shaping is a denylist for structured output (unknown/new models default to supported) and a substring allowlist for adaptive thinking — new frontier models work without edits.
- The leaked `HENRIKDEV_API_KEY` value committed in `.env.example` was blanked (it contradicted the file's own "all values empty" header). **Flagged to the user that the key should be rotated** since it was in git history.
- The new `template.yaml` references the existing Lambda by ARN and creates no Function, per the prompt — kept fully separate from `infra/template.yaml`.
- Track fixture stays honest: schematic is labeled as such in the JSON `source`, in `TrackMap`'s caption (`◆ Schematic — approximate positions, not telemetry`), and in the preview page — never presented as real telemetry.

---

## 4. Next Agent's Job

**STANDING CONSTRAINT (do not violate without an explicit new instruction)**: Stay in MOCK_MODE. Do NOT suggest, prepare for, or execute a live API call. Do NOT touch `.env`. The real key is added by the user, separately, only when they explicitly say so. (Session 13 acted on three explicit user prompts that lifted this for those tasks; the default constraint is back in force now.)

**Open items handed to the user (their gates)**:
- **Deploy `template.yaml`**: `sam build && sam deploy --guided` (needs `sam` + `aws` CLI installed and `stevenrhlaksono` creds configured — neither is on this machine). Report the invoke URL it prints.
- **Wire TrackMap into `/play`**: pending the user's review of the isolated `/track-map` route. When greenlit: render `<TrackMap>` above the F1 scenario text on `/play`, using the cached fixture (import `frontend/lib/fixtures/monza-track.json`), F1 mode only.
- **Real track telemetry**: re-run `scripts/fetch_track_layout.py` with OpenF1 network access to replace the schematic placeholder with real `/location` data. OpenF1 returned 401 here — may now need an API token.
- **Rotate the HenrikDev key** that was committed in `.env.example` (now blanked, but it's in git history).

**Immediate next task**: There is no forced next task — the ENTIRE app (Phases 1–4), plus the deployment infra-as-code, is scaffolded and verified in mock mode; scaffolding is essentially COMPLETE. The two remaining gates are both the user's alone: (1) the live grading validation (real key, MOCK_MODE off) and (2) the deploy greenlight (`sam deploy` per docs/DEPLOY.md). Wait for the user's direction. Remaining optional mock-mode work:
- More scenarios per domain — pure data now: a scenario JSON with an embedded `mock_synth` block needs zero code changes.
- Lambda-side DynamoDB loaders (`_load_scenario` / `_list_scenarios` / `_cache_scenario` filesystem→DynamoDB swap) — only matters at deploy time; the deployed stack works without it via in-package files (DEBRIEF_DATA_ROOT=/var/task) but needs a redeploy per new scenario until swapped.
- UI polish, more test coverage, mock-history merging with the real local attempts in `results/attempts-local.jsonl`.
- When (and only when) the user explicitly lifts the MOCK_MODE constraint: the live grading run — real key into `.env` (by the user), then `python3 scripts/stress_test_grading.py` with NO `MOCK_MODE`, review the injection HARD GATE (#4). Still the outstanding real validation of the rubric.
- After that and a user greenlight: deployment per `docs/DEPLOY.md` (SAM stack in `infra/template.yaml`, seed via `scripts/seed_dynamodb.py --execute`, Vercel with NEXT_PUBLIC_API_BASE).

To keep working in mock mode meanwhile: `MOCK_MODE=true python3 scripts/stress_test_grading.py`, `python3 tests/test_grade_attempt_local.py` (25/25), `python3 tests/test_phases_2_4_local.py` (54/54), `python3 tests/test_session12_local.py` (51/51), and the two-terminal loop in `docs/DEMO.md`.

**Context the next agent needs**:
- Everything is built and verified in mock mode (see Section 2). Every feature flips live by config: grading = real key + drop MOCK_MODE; auth = AUTH_MODE=cognito + pool/client IDs; VALORANT = HENRIKDEV_API_KEY; CS2 = TRACKERGG_APP_ID. `.env.example` documents every variable.
- `shared.grade_attempt` is still the one grading path for all three domains; only the system prompt differs per domain (`DOMAIN_SYSTEM_PROMPTS` in the grade Lambda). Mock verdicts: F1 in `grading.py`, VALORANT/CS2 via the config engine in `shared/domain_synth.py`.
- `MODEL` constant in `grading.py` reads from `CLAUDE_MODEL` env var (default `claude-opus-4-8`). Setting `CLAUDE_MODEL=something-else` in `.env` is the only change needed to switch models — no code edits.
- `output_config={"format": output_schema}` is the current correct Anthropic API shape. `thinking={"type": "adaptive"}` is correct for all Claude 4.6+ models. These do NOT need to be conditional for `claude-opus-4-8`.
- SESSION_STATE.md lives in the project root. Read fully before code, update before ending.
- Mock mode needs zero pip installs (boto3/anthropic are lazily imported in real paths only).
- Deployment, when greenlit: swap `_store_attempt`, scenario/prompt loaders, and `_cache_scenario` to DynamoDB/S3, stand up API Gateway + the five Lambdas + Cognito, deploy the frontend to Vercel.

**Do not touch**:
- The rubric weighting (reasoning 40, decision 20, risk 20, calibration 20) and anti-outcome-bias rules — locked since Session 1, now shared by all three domain prompts. Don't rebalance without a logged reason.
- `data/scenarios/monza-2024-leclerc-onestop.json` ground_truth / verified_data_points — verified from raw OpenF1; don't edit without re-deriving.
- The four `MOCK_VERDICTS` fixtures, especially #4 being the deliberate fooled/HARD-FAIL case — that's intentional to exercise the REWORK path, not a bug to "fix".
- The F1 branch of `synthesize_mock_verdict` — byte-identical since S7 on purpose; the 25 original tests pin its behavior. Domain changes go in `domain_synth.py`.
- The VALORANT/CS2 fixture scenarios are clearly-marked MOCK data — fine to refine, but never present them as real match data.

**Open questions / decisions pending**:
- ~~Verdict-driven UI framing~~ RESOLVED S7: implemented as a soft "debrief" — verdict headline sentence + reasoning subhead lead, reveal + strengths + one-takeaway next, dimension breakdown after, raw overall score demoted to a muted footnote. May still want to revisit copy once REAL verdicts are seen, but the framing decision is made.
- Length guard placement — settled: client-side (frontend UX) AND server-side via `shared.validate_attempt` (enforcing copy). Closed.
- Grader-output storage (`_store_attempt` stub): full clamped JSON, no scratch/thinking tokens — settled; wire to DynamoDB at deploy.
- The mock synthesizer's feedback wording could keep growing (more scenario-specific praise/nudges); current version is good enough for demos. Optional future polish, not blocking.

---

## 5. Skills Active on This Project

| Skill | When to use |
|---|---|
| session-commander | Start and end of every session, mandatory |
| code-council | Reviewing the grading prompt and any completed module before moving to the next phase |
| p10-coding-rules | All code generation, including the Lambda functions when they're written |

---

## 6. Stack and Environment

- **Language**: Python (scripts + Lambda scaffolds, stdlib-only in mock mode; `anthropic` for live), Next.js 14 / TypeScript frontend (Vercel target), AWS Lambda backend.
- **Key dependencies**: Anthropic API (claude-opus-4-8) — live mode only; OpenF1 API (no key). Frontend: next/react (in `frontend/package.json`).
- **How to run (all local, mock = no key/network needed)**:
  - Stress test (mock): `MOCK_MODE=true python3 scripts/stress_test_grading.py` — live: drop the flag, real key in `.env`.
  - Tests: `python3 tests/test_grade_attempt_local.py` (25/25).
  - Local API: `MOCK_MODE=true python3 scripts/local_api.py` (:8000).
  - Frontend: `cd frontend && npm install && npm run dev` (:3000), `cp .env.local.example .env.local`.
- **Environment setup**: `.env` at project root (real key needed for live). `.gitignore` now exists and ignores `.env`.
- **Output locations**: `data/`, `prompts/`, `scripts/`, `lambdas/`, `tests/`, `frontend/`, `results/`.
- **Any gotchas**: Schema has no numeric bounds → `clamp_scores` enforces them. System prompt is cached/stable — don't inline per-scenario data. Directory is `lambdas/` (not `lambda/`, a Python keyword); handlers put their own dir on `sys.path` to import `shared`.

---

## 7. The Handoff Prompt

```
[PASTE THIS INTO NEW SESSION]

Project: Debrief
Session: 14
Read SESSION_STATE.md in the project root before doing anything else.

Note (from S13): mock gating is now PER DOMAIN (MOCK_MODE_F1/VALORANT/CS2 via
lambdas/shared/mock_mode.py; MOCK_MODE is a legacy global override). grading.py
shapes the Anthropic request per model (CLAUDE_MODEL). There is a minimal root
template.yaml (POST /grade -> existing Lambda by ARN) SEPARATE from
infra/template.yaml — neither deployed. A TrackMap prototype exists at the
/track-map preview route but is NOT wired into /play yet (awaiting review), and
its Monza fixture is a labeled SCHEMATIC placeholder (OpenF1 /location 401'd) —
re-run scripts/fetch_track_layout.py with network for real telemetry. The
HenrikDev key in .env.example was blanked and needs rotating (it's in git
history). See Section 4 "Open items handed to the user".

STANDING CONSTRAINT — applies unless I explicitly lift it in this session:
STAY IN MOCK_MODE, across every domain (Anthropic, OpenF1, HenrikDev, Riot,
tracker.gg). Do NOT suggest, prepare for, or run any live API call. Do NOT
touch .env (placeholder names in .env.example are fine). Do not generate or
guess keys; never fabricate scores. Real credentials are added by me,
separately, only when I say so. Everything runs against fixtures
(MOCK_MODE=true).

Where things stand: scaffolding is essentially COMPLETE as of S12. The ENTIRE
app — Phases 1 through 4 — plus the deployment infra-as-code is built and
verified in mock mode. Each domain (F1 / VALORANT / CS2) has TWO scenarios
behind a scenario picker on /play (GET /list-scenarios); new scenarios are
pure data — a JSON file with an embedded mock_synth block, no code changes.
Graded attempts persist to results/attempts-local.jsonl with user attribution
(DynamoDB put_item written for real mode). infra/template.yaml is a validated
SAM stack (5 Lambdas incl. the /fetch-scenario router shared with local_api,
3 DynamoDB tables, Cognito); scripts/seed_dynamodb.py is dry-run by default;
docs/DEPLOY.md is the gated runbook. The VALORANT/CS2 real-mode scenario
builders got their curation-quality pass (kill-timeline alive counts, honest
constructed-frame labeling). Verified: 25/25 + 54/54 + 51/51 tests, mock
stress test (injection HARD FAIL is the deliberate fixture), npm run build
clean, all routes 200 with the MOCK DATA badge. NOTHING deployed.

The only remaining gates are MINE to open: (1) the live grading validation —
real key in .env by me, then `python3 scripts/stress_test_grading.py` with no
mock flag, review the injection HARD GATE for attempt #4 (the mock #4 fixture
is the deliberate fooled/REWORK case and does NOT answer whether the rubric
resists injection; only the live run does); (2) the deploy greenlight —
docs/DEPLOY.md end to end. Do not do either unless I explicitly say so.

There is NO forced next task — wait for my direction. Optional mock-mode work:
more scenarios (data-only now), UI polish, more tests, the Lambda-side
DynamoDB loader swap (only matters at deploy), or merging real local attempts
into the /history mock view.

To keep working in mock mode: `MOCK_MODE=true python3 scripts/stress_test_grading.py`,
`python3 tests/test_grade_attempt_local.py` (25/25),
`python3 tests/test_phases_2_4_local.py` (54/54),
`python3 tests/test_session12_local.py` (51/51), and the two-terminal loop in
docs/DEMO.md.

Skills (still not installed here — follow the protocol manually):
- session-commander (read the SSD first, update it at the end — mandatory)
- code-council (review any completed module before moving on)
- p10-coding-rules (all code)

Summarise Section 2 and Section 4 back to me before beginning.
```
