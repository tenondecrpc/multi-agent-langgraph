# chaos-fuzz-and-prompt-regression Specification

## Purpose
Defines the chaos, fuzz, and prompt regression testing program for the LangGraph Dev Squad. Ensures continuous validation of failure injection, contract fuzzing, and prompt-quality regression across the runtime pipeline.

## Requirements

### Requirement: Chaos Suite Covers Declared Scenarios

The chaos suite SHALL cover LLM garbage output, all-providers-down, sandbox crash and timeout, DB loss, Redis partition, worker kill, AZ failure, Vault unavailable, budget race, and noisy-neighbor. Each scenario SHALL assert expected observable behavior including SLO burn-rate alert, circuit-breaker state, DLQ depth, and graceful-shutdown checkpoint integrity.

#### Scenario: All providers down asserts fail-closed behavior
- **WHEN** the all-providers-down scenario is injected
- **THEN** the circuit breaker transitions to open across replicas
- **AND** the `all-providers-down.md` runbook alert fires
- **AND** no ticket progresses past the routing guard

#### Scenario: Redis partition keeps DLQ durable
- **WHEN** Redis is partitioned
- **THEN** existing DLQ rows remain queryable from PostgreSQL
- **AND** webhook idempotency still rejects duplicates via the unique constraint

### Requirement: Fuzz Suite Covers Public And Config Surfaces

Schemathesis SHALL fuzz the OpenAPI for webhooks and admin API. Hypothesis SHALL fuzz `GraphConfig` validators and routing-rule functions. Findings SHALL block CI when they expose hangs, crashes, or invariant violations.

#### Scenario: Hypothesis finds an invariant violation
- **WHEN** a property-based test discovers an input that violates an invariant
- **THEN** CI fails with the minimized input
- **AND** a regression fixture is captured for future runs

### Requirement: Prompt Regression Suite For Planner And Reviewer

LangSmith-backed evaluations SHALL score planner and reviewer outputs against versioned fixtures with deterministic metrics. CI SHALL block on regressions beyond tolerance.

#### Scenario: Planner output regresses on spec clarity
- **WHEN** a PR changes planner prompts or the planner node
- **THEN** the prompt-regression CI stage runs on planner fixtures
- **AND** a regression beyond tolerance blocks the merge

### Requirement: Nightly CI Stage And Monthly Game-Day

A `chaos-nightly` CI stage SHALL run the full chaos and fuzz suites. A monthly staging game-day SHALL replay the top-N scenarios with operator participation and produce a retrospective report.

#### Scenario: Monthly game-day produces a retrospective
- **WHEN** the monthly game-day completes
- **THEN** a retrospective under `docs/quality/` is published within one week
- **AND** action items are tracked back to owners
