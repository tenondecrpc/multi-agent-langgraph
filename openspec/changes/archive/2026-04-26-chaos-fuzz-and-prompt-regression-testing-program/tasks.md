## 1. Artifact Alignment

- [x] 1.1 Compose with Phase 7 quality-engineering-strategy and with all active and archived persistence, routing, and sandbox work.

## 2. Harness Scaffolding

- [x] 2.1 Add `backend/tests/chaos/`, `backend/tests/fuzz/`, `backend/tests/prompt_regression/` skeletons and shared fixtures.
- [x] 2.2 Ephemeral cluster bootstrap (kind or k3d) with Helm chart deployment.

## 3. Chaos Suite

- [x] 3.1 Implement scenarios: LLM garbage, all-providers-down, sandbox crash, sandbox timeout, DB loss, Redis partition, worker kill, AZ failure, Vault unavailable, budget race, noisy-neighbor.
- [x] 3.2 Observable assertions: circuit-breaker, DLQ, SLO burn-rate, graceful shutdown integrity.

## 4. Fuzz Suite

- [x] 4.1 Schemathesis on webhooks and admin API.
- [x] 4.2 Hypothesis on `GraphConfig` and routing-rule functions.

## 5. Prompt Regression

- [x] 5.1 LangSmith fixtures and deterministic scoring for planner and reviewer.
- [x] 5.2 CI stage `prompt-regression` on PRs touching prompts or agent nodes.

## 6. CI Cadence

- [x] 6.1 `chaos-nightly` stage runs full chaos and fuzz suites with report upload.
- [x] 6.2 Monthly game-day scheduling and on-call participation.

## 7. Verification

- [x] 7.1 `uv run --project backend pytest` succeeds on a focused PR subset.
- [x] 7.2 Nightly run green for one release before enforce.

## 8. Archive

- [x] 8.1 Archive after first monthly game-day retrospective is published.
