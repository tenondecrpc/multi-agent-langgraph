## Non-Goals

- Defining frontend graph editor interactions.
- Defining Kubernetes queue or service account manifests.
- Defining provider cost or budget policy.

## ADDED Requirements

### Requirement: Graph Runtime Is Config-Driven

The runtime workflow MUST be constructed from validated graph configuration rather than fixed source-code-only topology.

#### Scenario: Activatable graph config declares nodes and routes
- **WHEN** an admin prepares a candidate graph configuration
- **THEN** the configuration includes the nodes, edges, routes, and handler references needed to build the runtime workflow
- **AND** activation requires successful compilation and validation before the graph can become active

### Requirement: Protected Workflow Invariants Cannot Be Bypassed

An activatable v1 graph MUST preserve planner-owned artifact readiness, mandatory tests, mandatory review, pre-PR sync, and explicit escalation sinks.

#### Scenario: Graph that removes required guards is rejected
- **WHEN** a candidate graph omits the repo-write gate, tester, reviewer, pre-PR sync, or escalation requirements for a PR-reaching path
- **THEN** validation fails
- **AND** compile success alone is not enough to activate the graph

#### Scenario: Manual approval cannot become the normal success path
- **WHEN** a candidate graph inserts human approval
- **THEN** the approval may exist only on registered break-glass exception paths
- **AND** the normal success path remains autonomous-first

### Requirement: Registered Workflow Profile Remains Safe

The `ticket_to_pr_v1` profile MUST retain its protected system handlers and required guard semantics even when the surrounding graph is configurable.

#### Scenario: Required system handler cannot be removed
- **WHEN** a candidate config for the v1 ticket-to-PR profile removes or bypasses a required guard or system handler
- **THEN** activation is rejected
- **AND** the platform does not allow the protected profile to degrade into an unsafe arbitrary DAG
