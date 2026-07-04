# Debrief: Project Roadmap

**One line pitch:** Debrief is a teach-back learning app. Instead of testing recognition (flashcards), it shows you a real decision moment, has you explain your reasoning in plain English, and grades that explanation against what actually happened. Starting domain: F1 race strategy, with VALORANT and CS2 modes to follow.

**Why it's different:** Most study and stats tools test recognition or just show you numbers. Debrief tests whether you can reason and articulate, then gives specific feedback on what you got right, what you missed, and why, grounded in real historical outcomes rather than a made-up rubric.

---

## Naming conventions

Used consistently across the whole project so nothing is ambiguous later.

- GitHub repo: `debrief-app`
- Vercel project: `debrief`
- AWS resource prefix: `debrief-`
- Cognito user pool: `debrief-user-pool`
- API Gateway: `debrief-api`
- Lambda functions: `debrief-grade-attempt`, `debrief-fetch-f1-scenario`, `debrief-fetch-valorant-match`, `debrief-fetch-cs2-stats`, `debrief-auth-hook`
- DynamoDB tables: `debrief-users`, `debrief-attempts`, `debrief-f1-scenarios`, `debrief-match-cache`
- S3 buckets: `debrief-prod-raw-data`, `debrief-prod-assets`
- Environment variables: `ANTHROPIC_API_KEY`, `HENRIKDEV_API_KEY`, `TRACKERGG_APP_ID`, `RIOT_CLIENT_ID`, `RIOT_CLIENT_SECRET`, `AWS_REGION`, `DYNAMODB_TABLE_PREFIX`

---

## Phase 0: Setup (before any code)

Confirm these five accounts exist before starting. Each phase depends on one.

1. AWS account, with a Budget Alert set at $5 so nothing surprises you.
2. Vercel account, linked to GitHub.
3. Anthropic API key (console.anthropic.com), for grading calls.
4. GitHub account, with the `debrief-app` repo created.
5. Not yet needed: HenrikDev key, Riot developer account, tracker.gg developer account. Request those in Phase 3 and 4, not now, since keys can go stale if requested too early.
   **To do:**

- [ ] Create the `debrief-app` repo, empty, with a README stating the one line pitch.
- [ ] In AWS, create an IAM user for local development with programmatic access only, not the root account.
- [ ] In Vercel, connect the empty repo so every push auto-deploys.

---

## Phase 1: Core teach-back engine, F1 domain only (the MVP)

This is the only phase that matters for proving the idea works. Everything after this is expansion.

**What "teach-back grading" means concretely for F1:** the app shows a real historical race scenario (for example, lap 34 of a specific Grand Prix, gap to the car ahead, tire age, weather). The user types their explanation of what strategy call they would make and why. The AI grades that explanation against what actually happened in the real race and against sound strategic reasoning, then gives specific feedback on what they got right, what they missed, and why.

**To do:**

- [ ] Pull a handful of real race scenarios from OpenF1 (no key needed) and hand-pick 10 to 15 good "decision moments" (pit windows, safety car calls, tire choices) to seed `debrief-f1-scenarios`.
- [ ] Build the grading prompt: given the scenario, the user's explanation, and the real outcome data, produce a structured verdict (correct, partially correct, or incorrect) plus specific feedback. Test this manually in the Anthropic API console before wiring up any UI. This prompt is the entire product, so don't rush it.
- [ ] Build the Lambda functions: `debrief-fetch-f1-scenario` (serves a scenario) and `debrief-grade-attempt` (takes the user's answer, calls Claude, stores the result in `debrief-attempts`).
- [ ] Build the Vercel frontend: see scenario, type explanation, submit, see graded feedback. No accounts yet, no login, just a working loop.
- [ ] Deploy both sides and get one full round trip working end to end.
      **Timeline:** 2 to 3 weeks at a few hours most days. Do not rush this phase; a weak grading prompt sinks the whole project.

---

## Phase 2: Accounts, history, and polish

**To do:**

- [ ] Add Cognito (`debrief-user-pool`) so users can create an account and their attempts save to `debrief-users` and `debrief-attempts` under their own ID.
- [ ] Add a progress view: past scenarios attempted, score over time, which concepts keep getting missed.
- [ ] Basic UI polish: loading states, error states, a clean landing page that explains the idea in one screen.
- [ ] Record a 90 second demo video the moment this is stable. Do this now, don't wait for later phases. Something working end to end today beats a bigger unfinished thing later.
      **Timeline:** 1 to 2 weeks.

---

## Phase 3: VALORANT mode

**To do:**

- [ ] Join the HenrikDev Discord and request a free API key. Use it to build `debrief-fetch-valorant-match`, which pulls a signed-in user's own recent match history and round-by-round data.
- [ ] Design the VALORANT version of the teach-back prompt: given a round from the user's own match (economy, kills, utility used, outcome), ask them to explain what they'd have done differently, then grade it against the actual round outcome and sound decision making.
- [ ] The moment this prototype works, submit the Riot production key application (free, gated by approval, not cost) using this working prototype as evidence. Approval can take a while, so start this early.
- [ ] If the Riot key comes through before the demo, swap `debrief-fetch-valorant-match` to call the official API instead of HenrikDev. Same function, different data source underneath. Build the interface generically from the start to make this swap painless.
      **Timeline:** 2 weeks for the HenrikDev version. Riot approval timeline is out of your hands.

---

## Phase 4: CS2 mode

**To do:**

- [ ] Register as a tracker.gg developer and get a free app ID for their official CSGO stats API (this covers CS2).
- [ ] Build `debrief-fetch-cs2-stats`, reusing the same grading prompt pattern from VALORANT since the round structure is conceptually similar.
      **Timeline:** 1 week, since most of the pattern is already proven from Phase 3.

---

## Phase 5: Demo and portfolio prep

**To do:**

- [ ] Write the README: what it does, why it's different from existing tools, architecture diagram, which AWS services do real work and why.
- [ ] Record the final demo video, under 3 minutes, showing all three domains if ready, or F1 alone if that's what's polished.
- [ ] Write up the project as a short case study for interviews: the problem, why teach-back grading is different from flashcard tools, the AWS architecture, and what's next.

---

## Data sources (all free)

| Domain   | Source                   | Cost                          | Notes                                        |
| -------- | ------------------------ | ----------------------------- | -------------------------------------------- |
| F1       | OpenF1 API               | Free, no key                  | Historical data from 2023 onward             |
| VALORANT | HenrikDev API            | Free, request key via Discord | Prototyping source while Riot key is pending |
| VALORANT | Official Riot API        | Free, gated by approval       | Apply once prototype works                   |
| CS2      | tracker.gg Developer API | Free, official                | Covers CSGO/CS2                              |

The only cost in the whole stack is Claude API token usage during grading, which is small at this scale. AWS Lambda, DynamoDB, S3, Cognito, and API Gateway all fall under the Always Free tier for a project like this. Vercel Hobby tier is free for hosting.

---
