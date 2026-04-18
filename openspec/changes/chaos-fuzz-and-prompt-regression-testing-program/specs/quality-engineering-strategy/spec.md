## ADDED Requirements

### Requirement: Test Cadences Are Codified And Enforced

Unit and basic integration tests SHALL run on every PR. Chaos and full fuzz suites SHALL run nightly. Prompt regression SHALL run on every PR touching prompts or the planner or reviewer nodes and nightly. Monthly game-days SHALL run in staging with operator participation.

#### Scenario: Cadence regression blocks merge
- **WHEN** a PR attempts to disable a test cadence
- **THEN** CI blocks the merge unless the PR carries an explicit super_admin-approved exception with recorded rationale
