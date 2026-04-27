## ADDED Requirements

### Requirement: Credential Rotation Block Applies To Tenant Traffic

A tenant whose credentials are overdue SHALL be blocked from accepting new tenant traffic, not only admin operations. Active break-glass grants SHALL be the only override and SHALL be recorded in the audit trail.

#### Scenario: Overdue tenant cannot enqueue work
- **WHEN** a tenant credential is overdue and no break-glass grant is active
- **THEN** webhook acceptance, public API entry points, and queue enqueue requests for that tenant are rejected with reason `credential_rotation_overdue`

#### Scenario: Break-glass grant is single-use auditable
- **WHEN** a break-glass grant is active for the tenant
- **THEN** tenant traffic is accepted
- **AND** every accepted run records the grant identifier and expiration

### Requirement: Profile Drift Detection Alerts On Unsafe Combinations

A periodic job SHALL record the active deployment profile, database driver, and secret backend. The system SHALL alert when a non-`local` profile uses the in-memory database driver or the environment-only secret backend.

#### Scenario: Unsafe combination in production fires alert
- **WHEN** the periodic check observes `profile=production` and `db_driver=memory`
- **THEN** the alert fires with the offending sample
- **AND** the alert label points to the boot-safety runbook
