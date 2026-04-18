## ADDED Requirements

### Requirement: Budget Reservations Are Race-Free Across Replicas

Per-ticket and per-team budget reservations SHALL be atomic across horizontally-scaled workers. The adapter SHALL use a Redis Lua script to decrement and check limits while writing a durable row to PostgreSQL in the same unit of work.

#### Scenario: Concurrent reservations never exceed the cap
- **WHEN** two workers attempt simultaneous reservations that would together exceed a per-team cap
- **THEN** exactly one reservation succeeds
- **AND** the failing reservation receives a typed budget-exhausted error with audit evidence

#### Scenario: PostgreSQL is authoritative on replay and reconciliation
- **WHEN** Redis state is reset after an incident
- **THEN** the adapter reconciles Redis counters from PostgreSQL budget rows
- **AND** subsequent reservations respect the reconciled counters

### Requirement: Budget State Is Durable And Auditable

Every reservation, commit, release, and denial SHALL write a row to the durable budget ledger in PostgreSQL with tenant, team, ticket, actor, rationale, and evidence summary.

#### Scenario: Denial leaves an audit trail
- **WHEN** a budget denial occurs
- **THEN** a `budget_denials` row is written in the same transaction as the reservation attempt
- **AND** the audit log references the row
