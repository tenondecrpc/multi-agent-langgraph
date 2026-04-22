# worker-queue-operations Specification

## Purpose
TBD - created by archiving change phase-2-platform-and-sandbox. Update Purpose after archive.
## Requirements
### Requirement: Weighted-Fair Queue Dispatch

Worker dispatch MUST preserve tenant fairness with bounded concurrency instead of allowing a single tenant to monopolize the execution pool.

#### Scenario: Tenant fairness is enforced
- **WHEN** multiple tenants have queued jobs at the same time
- **THEN** the dispatcher selects work using weighted fairness rather than raw FIFO across the whole pool
- **AND** per-tenant concurrency limits prevent one tenant from occupying the full worker fleet

#### Scenario: Starvation protection overrides weight
- **WHEN** a queued job has waited beyond the configured starvation threshold
- **THEN** the dispatcher promotes that job ahead of normal weighting
- **AND** the promotion is treated as a fairness safeguard rather than a permanent priority change

### Requirement: Worker Draining Preserves Checkpoint Boundaries

Worker shutdown and rescheduling MUST preserve checkpoint safety instead of abandoning in-flight progress.

#### Scenario: Graceful shutdown drains safely
- **WHEN** a worker receives a termination signal for rollout or scaling
- **THEN** it stops accepting new jobs and allows active work to reach a checkpoint-safe boundary
- **AND** unfinished work remains resumable rather than silently lost

### Requirement: Dead-Letter Capture Is Mandatory

Irrecoverable job failures MUST land in a dead-letter workflow that operators can inspect and retry later.

#### Scenario: Failed job is captured for later action
- **WHEN** a job exceeds its retry or recovery boundary
- **THEN** the job metadata and failure context are preserved in a dead-letter queue or store
- **AND** the failure does not disappear from operator visibility

### Requirement: Worker Capacity Is Planned For Horizontal Scaling

The platform MUST plan for horizontally scaled API and worker pools with explicit autoscaling boundaries.

#### Scenario: Worker scaling assumptions are defined
- **WHEN** the platform workload model is implemented later
- **THEN** the primary worker deployment includes explicit minimum and maximum capacity expectations
- **AND** scaling policy is based on queue or active-job pressure rather than ad hoc manual intervention alone

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

