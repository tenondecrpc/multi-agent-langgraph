## Why

The constitution lists chaos, fuzz, and prompt regression coverage as Tier 1 mandatory. `STATUS.md` confirms `chaos-fuzz-and-prompt-regression-testing-program` is still open. The repository contains empty placeholder directories `backend/tests/chaos`, `backend/tests/fuzz`, and `backend/tests/prompt_regression`, plus a `chaos-nightly.yml` workflow and a `prompt-regression.yml` workflow, but no actual scenarios are exercised. The current 202-passing test suite is almost entirely contract tests; behavior under partial failure, malformed input, and prompt drift is not validated.

## What Changes

- Define the chaos scenario catalog: persistence outage, Redis split-brain, provider quota exhaustion, webhook flood, mid-traffic secret rotation, sandbox runtime crash, control-plane snapshot corruption, KEK rotation under load, network policy breach simulation, and DLQ overflow.
- Define the fuzz target catalog: webhook payload, Jira event normalizer, OpenAPI inputs at the public API surface, escalation reason coercion, RAG retrieval inputs, billing CSV import, admission exception payloads.
- Define the prompt regression catalog: planner clarification loop, coder generation, reviewer rejection criteria, escalation triggers, role boundary leakage probes, prompt-injection corpus.
- Define the offline-first execution contract: every chaos/fuzz/prompt suite must be runnable in `air_gapped` mode with deterministic seeds and no vendor egress.
- Define CI integration: nightly chaos run, weekly fuzz run with shrunk-corpus persistence, prompt-regression on every PR that touches agent prompts or graph routing.
- Define escalation: chaos failures open SEV3 incidents automatically; prompt regressions block merge; fuzz crashes are written to a corpus directory and triaged within an SLO.

## Capabilities

### Modified Capabilities

- `chaos-fuzz-and-prompt-regression`: enumerate scenarios, fuzz targets, and prompt suites, with offline-first execution and merge-blocking semantics.
- `quality-engineering-strategy`: integrate chaos/fuzz/prompt regression into the canonical test ladder alongside unit, integration, and E2E.

## Tier Classification

This change addresses a Tier 1 non-negotiable. It does not weaken any rule.

## Non-Goals

- Replacing `pytest` with another framework.
- Live chaos experiments against customer production clusters; chaos runs target staging or ephemeral clusters only.
- LLM evaluation of agent quality beyond regression; capability scoring is out of scope.
- New observability infrastructure; reuse Prometheus and existing alert rules.

## Operational Impact

- Nightly CI cost increases; budget must be approved by operators.
- Prompt regression demands a pinned model snapshot or recorded fixtures so air-gapped runs are deterministic.
- Fuzz corpus storage requires a path under `backend/tests/fuzz/corpora/` checked into git for shrunk minimal cases.

## Risk

- Flaky chaos tests can erode trust if they fail intermittently without root cause.
- Prompt regression suites can over-fit to a specific model version and break on legitimate upgrades.
- Air-gapped determinism requires fixtures that can drift from real provider outputs.

## Rollback / Degradation

- Chaos suites are gated behind a feature flag; a flagged disable path must remain available.
- Prompt regression failures must produce diff artifacts rather than only a pass or fail bit.
- Fuzz timeouts must default to a bounded budget per CI run.
