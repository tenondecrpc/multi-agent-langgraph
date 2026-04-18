## ADDED Requirements

### Requirement: Backup And Restore Drills Cover Every New Persistence Surface

Backup and restore drills SHALL exercise the PostgreSQL tables introduced or extended by the persistence backbone, including `runs`, `graph_versions`, `agent_versions`, `snapshots`, `run_snapshot_bindings`, `audit_events`, `budget_reservations`, `budget_charges`, `budget_denials`, `metering_facts`, `metering_hourly_rollups`, `model_catalog`, `provider_health_events`, `dead_letter_records`, and `webhook_idempotency_records`, and SHALL cover Redis outage scenarios that exercise the fail-closed and reconciliation paths.

#### Scenario: Quarterly DR drill validates RPO and RTO
- **WHEN** the quarterly DR drill runs
- **THEN** the drill restores a recent snapshot to a scratch environment
- **AND** it verifies that RPO and RTO targets are met for each surface listed above
- **AND** the drill report is retained as audit evidence

#### Scenario: Redis outage drill exercises reconciliation
- **WHEN** the drill simulates a Redis cluster failure
- **THEN** the budget, circuit-breaker, and idempotency subsystems exhibit the documented fail-closed behavior
- **AND** after Redis recovery the adapters reconcile counters from PostgreSQL authoritative records
