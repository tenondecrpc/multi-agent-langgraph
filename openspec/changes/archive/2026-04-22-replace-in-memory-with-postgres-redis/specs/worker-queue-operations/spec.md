## ADDED Requirements

### Requirement: ARQ On Redis Is The Queue Transport And PostgreSQL Owns Durable DLQ

Ticket work SHALL be enqueued, dispatched, and consumed via ARQ on Redis 7 Cluster. Dead-letter records SHALL be persisted in a PostgreSQL `dead_letter_records` table and SHALL be retained according to the data-retention policy.

#### Scenario: Job terminally fails and lands in durable DLQ
- **WHEN** a job exhausts its retry policy or hits a non-recoverable error
- **THEN** a row is written to `dead_letter_records` with tenant, team, run, failure reason, and checkpoint reference
- **AND** the ARQ job is removed from the active queue
- **AND** the event is observable via DLQ-depth metrics

#### Scenario: Redis outage does not lose DLQ history
- **WHEN** Redis is rebuilt after an outage
- **THEN** previously written DLQ records remain queryable from PostgreSQL
- **AND** operators can replay them from the DLQ surface

### Requirement: Weighted-Fair Dispatch Uses Redis-Backed Counters

The weighted-fair dispatcher SHALL read in-flight per-tenant counters from Redis and SHALL NOT rely on any process-local map. Starvation thresholds and per-tenant concurrency limits remain config-driven.

#### Scenario: Counters are consistent across replicas
- **WHEN** multiple worker replicas select the next job concurrently
- **THEN** the Redis counters reflect every assignment atomically
- **AND** no two workers accept a job that would exceed a tenant's concurrency limit

### Requirement: Drain And Checkpoint Release Are Coordinated Through Redis Leases

Worker drain SHALL be represented as a Redis lease keyed by worker identity. A worker that is draining SHALL NOT accept new assignments and SHALL flush to a checkpoint boundary before releasing its lease.

#### Scenario: SIGTERM drains to checkpoint boundary
- **WHEN** a worker receives SIGTERM
- **THEN** it acquires the drain lease, stops pulling new jobs, completes the current job to the next checkpoint boundary, writes the checkpoint reference to PostgreSQL, releases the lease, and exits
- **AND** the readiness probe is failing throughout the drain
