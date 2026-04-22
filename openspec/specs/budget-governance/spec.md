# budget-governance Specification

## Purpose
TBD - created by archiving change phase-4-llm-governance-and-metering. Update Purpose after archive.
## Requirements
### Requirement: Ticket And Team Budget Caps Are Mandatory

The platform MUST enforce hard budget caps for individual runs and for team-level daily and monthly usage.

#### Scenario: Run stays within ticket and team budgets
- **WHEN** a model invocation is requested for a run with available ticket and team budget
- **THEN** the runtime may continue after budget reservation succeeds

#### Scenario: Budget exhaustion stops normal progress
- **WHEN** a requested invocation would exceed the configured ticket, daily team, or monthly team cap
- **THEN** the invocation is blocked
- **AND** the run escalates with a budget-exhaustion reason instead of continuing silently

### Requirement: Budget Reservation Is Atomic

Budget enforcement MUST use atomic reservation across the relevant counters so concurrent calls cannot overspend shared caps.

#### Scenario: Concurrent calls cannot overspend budget
- **WHEN** multiple workers or nodes attempt model invocations that draw from the same budget pools
- **THEN** the reservation logic applies all required decrements atomically or rolls them back together
- **AND** the combined calls cannot exceed the configured cap through a check-then-act race

### Requirement: Reservation Settlement Reconciles Actual Cost

Budget reservations MUST reconcile estimated and actual cost after each invocation, including failed-call cleanup.

#### Scenario: Over-reserved budget is refunded
- **WHEN** actual invocation cost is lower than the reserved worst-case estimate
- **THEN** the unused amount is credited back to the relevant budget pools during settlement

#### Scenario: Orphaned reservation is recovered
- **WHEN** a reserved invocation fails before settlement completes
- **THEN** background reconciliation can identify and release the orphaned reservation
- **AND** the budget does not remain permanently reduced by a failed call path

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

