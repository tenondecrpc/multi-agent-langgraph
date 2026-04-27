## ADDED Requirements

### Requirement: Test Ladder Includes Chaos, Fuzz, And Prompt Regression Layers

The canonical test ladder SHALL include unit, integration, contract, end-to-end, chaos, fuzz, and prompt regression layers. Each layer SHALL have a documented trigger, budget, and escalation sink.

#### Scenario: Layer table is queryable from the spec
- **WHEN** an operator inspects the quality strategy spec
- **THEN** every layer in the ladder lists its trigger, time budget, escalation sink, and merge-blocking semantics

### Requirement: Failure Artifacts Are Triagable

Every failure in chaos, fuzz, or prompt regression SHALL produce a structured artifact with seed, fault model or input, and the diverging assertion. The artifact SHALL be uploaded by CI for triage.

#### Scenario: Triage agent has enough to reproduce
- **WHEN** an operator opens a failure artifact
- **THEN** the artifact contains the seed, fault description, and either a recorded fixture diff or a shrunk crashing input
- **AND** the artifact is sufficient to reproduce locally without re-running the failing CI job
