## ADDED Requirements

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
