## ADDED Requirements

### Requirement: Agent Handler Registry Resolves From The Persisted Active Snapshot

The agent handler registry SHALL resolve handlers from the PostgreSQL-persisted active snapshot. A process-local cache keyed by `snapshot_id` is permitted for performance and SHALL be invalidated by a Redis pub/sub event on activation or rollback.

#### Scenario: Activation propagates to every replica within the freshness window
- **WHEN** an operator activates a new snapshot
- **THEN** a Redis pub/sub message is published on the control-plane channel
- **AND** every replica invalidates its cached registry within the freshness SLO
- **AND** new runs pin the new snapshot while in-flight runs keep their pinned snapshot

#### Scenario: Cache miss falls back to PostgreSQL
- **WHEN** a process starts or receives an invalidation event
- **THEN** it reloads the handler registry from PostgreSQL
- **AND** it never serves runs from a stale snapshot
