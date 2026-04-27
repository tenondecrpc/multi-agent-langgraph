## ADDED Requirements

### Requirement: Non-Local Profiles Refuse To Start On In-Memory Adapters

When `BACKEND_DEPLOYMENT_PROFILE` is `staging`, `production`, `air_gapped`, or `recovery`, the backend SHALL refuse to start unless PostgreSQL, Redis, the configured secret backend, and the model catalog source are reachable. In-memory fallbacks SHALL be available only in `local` and `test` profiles.

#### Scenario: Production boot without database fails fast
- **WHEN** the pod starts in `production` without a database URL
- **THEN** startup fails with a structured boot-failure log
- **AND** the pod does not enter `Ready` state

#### Scenario: Local boot still allows in-memory adapters
- **WHEN** the pod starts in `local` without a database URL
- **THEN** startup succeeds using in-memory adapters
- **AND** readiness reports `local` profile

### Requirement: Readiness Probe Is Strict Outside Local And Test

In `staging`, `production`, `air_gapped`, and `recovery` profiles, the readiness probe SHALL report `not_ready` when the database, Redis, or migration state is `not_configured`. The current tolerance only applies to `local` and `test`.

#### Scenario: Production readiness fails on missing migration state
- **WHEN** the pod runs in `production` and the migration state reports `not_configured`
- **THEN** `/readyz` returns `503` with reason `database_unhealthy` or `migration_drift`
- **AND** the response includes the runbook URL

### Requirement: Recovery Profile Closes Webhook Acceptance

The `recovery` profile SHALL boot with the same persistence and secret guarantees as `production`, but SHALL refuse to accept any webhook traffic.

#### Scenario: Recovery boot rejects webhook
- **WHEN** the pod runs in `recovery` profile and a webhook arrives
- **THEN** the pod returns a structured rejection with reason `recovery_profile_active`
- **AND** the readiness probe stays `ok` for management endpoints
