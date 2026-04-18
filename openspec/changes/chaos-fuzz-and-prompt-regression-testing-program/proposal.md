## Why

Comprehensive testing (unit, integration, E2E, chaos, fuzz, prompt regression) is a Tier 1 non-negotiable. PLAN.md lists specific scenarios: LLM garbage output, all-providers-down, sandbox crash and timeout, DB loss, Redis partition, worker kill, AZ failure, Vault unavailable, budget race, noisy-neighbor, schemathesis fuzzing on webhooks and admin API, hypothesis fuzzing on GraphConfig, and LangSmith-backed planner and reviewer prompt regression. Phase 7 set the quality direction; this change delivers the programs and CI wiring.

## What Changes

- Chaos suite under `backend/tests/chaos/` with each scenario above expressed as an invasion-style test against an ephemeral cluster or container stack; `chaos-nightly` CI stage runs them and publishes a report.
- Fuzz suite: schemathesis contract-fuzz against the OpenAPI for webhooks and admin API; hypothesis property-based tests on `GraphConfig` validators and routing rules.
- Prompt regression suite: LangSmith-backed evaluations of planner and reviewer fixtures with deterministic metrics; CI `prompt-regression` stage blocks on regressions beyond tolerance.
- Monthly staging game-day schedule replaying top-N chaos scenarios with on-call participation.
- Reports land in `docs/quality/` and feed the SLO/error-budget dashboards.

## Capabilities

### New Capabilities

- `chaos-fuzz-and-prompt-regression`: scenarios, harness, CI stages, game-day cadence, report retention.

### Modified Capabilities

- `quality-engineering-strategy`: adds the specific test surfaces and cadences.

## Impact

- Code: new `backend/tests/chaos/`, `backend/tests/fuzz/`, `backend/tests/prompt_regression/`.
- CI: new stages `chaos-nightly` and `prompt-regression`; `pr-check` runs a focused fuzz subset.
- Secrets: prompt regression fixtures never contain real customer content; use synthetic tickets.
- Docs: game-day playbook and report archive.
- Constitution alignment: Tier 1 preserved.
