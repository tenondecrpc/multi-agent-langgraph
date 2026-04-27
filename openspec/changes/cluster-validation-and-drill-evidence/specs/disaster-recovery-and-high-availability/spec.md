## ADDED Requirements

### Requirement: Drill Evidence Is Structured And Time-Bounded

Every drill run SHALL produce a structured evidence bundle under `docs/drills/evidence/<drill>/<run-id>/` with metadata, inputs, observations, metrics, optional screenshots, and a status file. A signed timestamp SHALL be included.

#### Scenario: Quarterly DR drill produces evidence
- **WHEN** the DR backup-and-restore drill completes
- **THEN** the evidence directory contains the documented files
- **AND** the metadata file includes a signed timestamp and a hash of the run

### Requirement: Stale Evidence Is Treated As Missing

Evidence older than its validity window SHALL be treated as missing. Operators SHALL NOT consult expired evidence to advance gated decisions.

#### Scenario: Expired DR evidence blocks audit claim
- **WHEN** a DR drill evidence bundle is older than 120 days
- **THEN** the freshness check reports `expired`
- **AND** the admission flip gate refuses to consult that evidence

### Requirement: Destructive Drills Use Synthesized Tenants

Destructive drills (KEK rotation, tenant erasure, DR restore) SHALL run on synthesized tenants in staging or an ephemeral lab. They SHALL NOT target real customer tenants.

#### Scenario: Tenant erasure drill targets fixture tenant
- **WHEN** the GDPR erasure drill runs
- **THEN** the drill operates on a fixture tenant identifier reserved for drills
- **AND** the dual-control approval records both approver identities
