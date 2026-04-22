# observability-and-incident-response Specification

## Purpose
TBD - created by archiving change phase-7-observability-reliability-and-release. Update Purpose after archive.
## Requirements
### Requirement: Product Observability Covers Logs, Metrics, And Traces

The platform MUST emit structured logs, operational metrics, distributed traces, and health probes across its core components.

#### Scenario: Backend activity is observable across components
- **WHEN** API, worker, or sandbox activity occurs
- **THEN** the platform emits structured logs with the correlation and tenant context needed for investigation
- **AND** relevant metrics and traces are available for the same activity path

#### Scenario: Health surfaces remain explicit
- **WHEN** operators or orchestration systems need service health
- **THEN** the platform exposes health and readiness signals for the relevant components
- **AND** those signals can be consumed by deployment and monitoring systems

### Requirement: Incident Response Is Part Of The Product Contract

The platform MUST define incident severity, runbook expectations, on-call handling, and public status communication behavior.

#### Scenario: Pager-worthy incident has a documented path
- **WHEN** a severe customer-visible failure occurs
- **THEN** the product's operational model includes severity handling, runbook references, and public communication expectations
- **AND** missing runbook coverage is treated as an operational gap rather than acceptable ambiguity

#### Scenario: Public status communication remains supported
- **WHEN** the platform experiences customer-visible degradation
- **THEN** operators can publish component-level status updates through the documented status communication surface

### Requirement: Dashboards Are Shipped As Part Of Operations

The product MUST plan for packaged dashboards that expose the key operational surfaces needed by operators.

#### Scenario: Operators can inspect core platform health
- **WHEN** the platform is deployed
- **THEN** packaged dashboards expose the critical business, LLM, queue, and infrastructure signals needed for day-to-day operation

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

