# graph-configuration-runtime Specification

## Purpose
TBD - created by archiving change phase-5-config-driven-graph-and-admin-control. Update Purpose after archive.
## Requirements
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

### Requirement: Runtime Graph Loads Configuration From The Persisted Active Snapshot

The runtime graph SHALL load its topology, route rules, and interrupt policy from the active PostgreSQL snapshot. No process-local authoritative copy MAY exist. The existing repo-write gate, mandatory test, review, diff-size guard, forbidden-path guard, and pre-PR sync invariants remain unchanged.

#### Scenario: Fresh replica boots without an active snapshot
- **WHEN** a pod starts and no active snapshot exists in PostgreSQL
- **THEN** readiness fails with a structured reason
- **AND** the admin API surface exposes an actionable error
- **AND** no ticket is dispatched to the graph

#### Scenario: Active snapshot change does not affect pinned runs
- **WHEN** the active snapshot changes mid-flight
- **THEN** runs retain the snapshot pinned at acceptance time
- **AND** only newly accepted runs use the new snapshot

