# quality-engineering-strategy Specification

## Purpose
Defines the product quality strategy across unit, integration, contract, end-to-end, chaos, fuzz, prompt-regression, static analysis, coverage, and cadence gates.
## Requirements
### Requirement: Quality Coverage Includes More Than Unit Tests

The product MUST plan unit, integration, end-to-end, chaos, fuzz, and prompt-regression coverage.

#### Scenario: Test strategy spans the full execution path
- **WHEN** the test program is implemented later
- **THEN** it covers isolated units, integrated service behavior, full ticket-to-PR flows, failure injection, protocol fuzzing, and prompt-quality regression
- **AND** the system is not declared production-ready on unit coverage alone

### Requirement: Prompt Regression Is First-Class

Planner, reviewer, and other prompt-sensitive behavior MUST be guarded by regression evaluation rather than manual spot-checking only.

#### Scenario: Prompt change triggers structured evaluation
- **WHEN** a prompt or prompt-relevant config changes
- **THEN** the change can be evaluated against known-good fixtures or schemas
- **AND** regressions are detectable before rollout

### Requirement: Chaos And Edge-Case Failures Are Planned

The quality program MUST include chaos and failure-mode coverage for the critical operational edges called out in the product plan.

#### Scenario: Critical failure modes remain in scope
- **WHEN** the chaos or resilience test program is defined
- **THEN** it includes scenarios such as provider outage, sandbox failure, database loss, Vault outage, or similar critical edges from the plan
- **AND** those scenarios are not left to ad hoc manual testing only

### Requirement: Automated Integration Suite Exercises Real Dependencies

The integration test layer MUST run on every pull request and exercise the product against real PostgreSQL, Redis, and sandbox runtimes rather than only mocked substitutes.

#### Scenario: Integration suite runs on every pull request
- **WHEN** a pull request targets the main branch
- **THEN** the integration test layer executes against real PostgreSQL and Redis (for example through testcontainers) and against a sandboxed code-execution path that mirrors the production runtime contract
- **AND** a merge is not permitted while the required integration layer is skipped or failing

#### Scenario: Cross-cutting flows are validated end-to-end before release
- **WHEN** the release pipeline promotes a build toward production
- **THEN** the pipeline validates webhook intake, graph execution with checkpointing, budget and failover behavior, and PR creation guards against a staging environment before promotion proceeds

### Requirement: SOLID And Static Analysis Gate The Product Codebase

The product codebase MUST be gated by linting, type or static analysis, complexity and duplication checks, and SOLID-aligned code review expectations before any change is merged.

#### Scenario: Static quality gates run in CI
- **WHEN** a pull request is opened against the product repository
- **THEN** the pipeline runs linting, type or static analysis, complexity, and duplication checks for the changed languages and stacks
- **AND** a merge is blocked while those gates fail

#### Scenario: SOLID compliance is part of review
- **WHEN** a reviewer approves a change that introduces or modifies a module, class, or public interface
- **THEN** the review process validates the change against single-responsibility, open-closed, Liskov substitution, interface segregation, and dependency-inversion expectations as a first-class reviewer checklist item
- **AND** SOLID violations are not silently approved as style preferences

### Requirement: Coverage Thresholds Are Declared And Enforced

The quality program MUST declare minimum coverage thresholds for unit and integration layers and MUST fail the pipeline when a change drops measured coverage below the declared floor without an explicit, auditable waiver.

#### Scenario: Coverage regression blocks merge
- **WHEN** a pull request reduces measured unit or integration coverage below the declared floor
- **THEN** the pipeline fails the change
- **AND** an approved waiver is required to merge, recorded in the change trail rather than silently bypassed

### Requirement: Test Cadences Are Codified And Enforced

Unit and basic integration tests SHALL run on every PR. Chaos and full fuzz suites SHALL run nightly. Prompt regression SHALL run on every PR touching prompts or the planner or reviewer nodes and nightly. Monthly game-days SHALL run in staging with operator participation.

#### Scenario: Cadence regression blocks merge
- **WHEN** a PR attempts to disable a test cadence
- **THEN** CI blocks the merge unless the PR carries an explicit super_admin-approved exception with recorded rationale

### Requirement: Test Ladder Includes Chaos, Fuzz, And Prompt Regression Layers

The canonical test ladder SHALL include unit, integration, contract, end-to-end, chaos, fuzz, and prompt regression layers. Each layer SHALL have a documented trigger, time budget, escalation sink, artifact format, and merge-blocking semantics. Contract tests SHALL remain distinct from chaos, fuzz, and prompt regression: contract tests validate declared interfaces and workflow invariants, while chaos, fuzz, and prompt regression validate behavior under faults, malformed inputs, and prompt drift.

#### Scenario: Layer table is queryable from the spec
- **WHEN** an operator inspects the quality strategy spec
- **THEN** every layer in the ladder lists its trigger, time budget, escalation sink, and merge-blocking semantics

#### Scenario: Chaos layer does not duplicate contract tests
- **WHEN** a maintainer reviews the test ladder
- **THEN** the contract layer is responsible for stable API, schema, and workflow contract checks
- **AND** the chaos, fuzz, and prompt regression layers are responsible for injected failure, generated input, and recorded prompt-fixture checks

### Requirement: Failure Artifacts Are Triagable

Every failure in chaos, fuzz, or prompt regression SHALL produce a structured artifact with seed, fault model or input, expected escalation reason when applicable, registered sink, and the diverging assertion. The artifact SHALL be uploaded by CI for triage and SHALL include a local reproduction command that works in connected and `air_gapped` profiles.

#### Scenario: Triage agent has enough to reproduce
- **WHEN** an operator opens a failure artifact
- **THEN** the artifact contains the seed, fault description, and either a recorded fixture diff or a shrunk crashing input
- **AND** the artifact is sufficient to reproduce locally without re-running the failing CI job

#### Scenario: Fuzz triage SLA is visible
- **WHEN** a fuzz crash artifact is uploaded
- **THEN** CI creates or updates an item in `ops://fuzz-triage`
- **AND** the item records the two-business-day triage SLA and current decision state
