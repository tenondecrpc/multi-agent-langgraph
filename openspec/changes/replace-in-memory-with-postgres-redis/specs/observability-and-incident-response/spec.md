## ADDED Requirements

### Requirement: Persistence Metrics, Logs, And Traces Are First-Class

The persistence backbone SHALL emit metrics for connection-pool utilisation and wait p95, query p95 per subsystem, Redis command p95, circuit-breaker state transitions, DLQ depth, webhook-dedupe hit rate, budget-reservation denials, and applied migration version. Every repository, ledger, registry, and guard method SHALL be wrapped in an OpenTelemetry span with `tenant_id`, `team_id`, `run_id`, `subsystem`, and `operation` attributes. Logs SHALL never include ciphertext, plaintext secrets, or key material.

#### Scenario: Pool saturation fires a burn-rate alert
- **WHEN** pool utilisation exceeds the configured high-water mark for the alert window
- **THEN** an alert routes through the standard alerting pipeline
- **AND** the associated runbook link references the persistence module

#### Scenario: DLQ growth triggers an incident
- **WHEN** DLQ depth grows above the configured threshold
- **THEN** an alert fires with tenant and failure-reason breakdowns
- **AND** the runbook covers replay and escalation procedures

### Requirement: Migration And Snapshot Status Are Visible In Health And UI

Migration version, active snapshot id, and adapter readiness SHALL be exposed on the persistence health surface and on the admin UI status panel.

#### Scenario: Admin sees migration drift at a glance
- **WHEN** an operator opens the status panel
- **THEN** the UI shows expected vs applied migration version and active snapshot id
- **AND** it flags drift with an accessible warning that meets the AA contrast and keyboard-reachability non-negotiable subset
