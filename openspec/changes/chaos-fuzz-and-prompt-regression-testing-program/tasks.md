## 1. Artifact Alignment

- [ ] 1.1 Compose with Phase 7 quality-engineering-strategy and with all active and archived persistence, routing, and sandbox work.

## 2. Harness Scaffolding

- [ ] 2.1 Add `backend/tests/chaos/`, `backend/tests/fuzz/`, `backend/tests/prompt_regression/` skeletons and shared fixtures.
- [ ] 2.2 Ephemeral cluster bootstrap (kind or k3d) with Helm chart deployment.

## 3. Chaos Suite

- [ ] 3.1 Implement scenarios: LLM garbage, all-providers-down, sandbox crash, sandbox timeout, DB loss, Redis partition, worker kill, AZ failure, Vault unavailable, budget race, noisy-neighbor.
- [ ] 3.2 Observable assertions: circuit-breaker, DLQ, SLO burn-rate, graceful shutdown integrity.

## 4. Fuzz Suite

- [ ] 4.1 Schemathesis on webhooks and admin API.
- [ ] 4.2 Hypothesis on `GraphConfig` and routing-rule functions.

## 5. Prompt Regression

- [ ] 5.1 LangSmith fixtures and deterministic scoring for planner and reviewer.
- [ ] 5.2 CI stage `prompt-regression` on PRs touching prompts or agent nodes.

## 6. CI Cadence

- [ ] 6.1 `chaos-nightly` stage runs full chaos and fuzz suites with report upload.
- [ ] 6.2 Monthly game-day scheduling and on-call participation.

## 7. Verification

- [ ] 7.1 `uv run --project backend pytest` succeeds on a focused PR subset.
- [ ] 7.2 Nightly run green for one release before enforce.

## 8. Archive

- [ ] 8.1 Archive after first monthly game-day retrospective is published.
