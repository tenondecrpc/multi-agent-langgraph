# graph-shadow-mode Specification

## Purpose
TBD - created by archiving change phase-5-config-driven-graph-and-admin-control. Update Purpose after archive.
## Requirements
### Requirement: Shadow Runs Are Read-Only By Design

Candidate graph configurations MUST be testable through shadow runs that cannot mutate live repositories or Jira state.

#### Scenario: Shadow run cannot perform write actions
- **WHEN** a candidate graph is executed in shadow mode
- **THEN** the run uses read-only credentials and isolated execution surfaces
- **AND** repository writes, PR creation, and Jira write actions are blocked by more than one layer of defense

### Requirement: Shadow Mode Uses Defense In Depth

Shadow execution MUST rely on separate credentials, queueing, worker identity, network policy, and application flags rather than a single read-only toggle.

#### Scenario: Shadow isolation remains intact if one layer is bypassed
- **WHEN** application code or configuration is misused during a shadow run
- **THEN** outer layers such as credential scope, queue segregation, or network restrictions still prevent write-side effects

### Requirement: Activation Uses Measured Comparison

Shadow mode MUST produce candidate-versus-active comparison results that gate activation.

#### Scenario: Candidate regression blocks activation
- **WHEN** a candidate graph materially degrades success rate or materially increases cost beyond the configured activation thresholds
- **THEN** the system blocks ordinary activation
- **AND** any override requires explicit operator acknowledgment recorded in audit context

#### Scenario: Shadow evidence is persisted
- **WHEN** shadow runs complete
- **THEN** the system stores outcome, retry, and cost comparison data for review
- **AND** activation decisions can reference that persisted evidence instead of relying on operator memory

