## ADDED Requirements

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
