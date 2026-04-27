## ADDED Requirements

### Requirement: Credential Rotation Block Applies To Tenant Traffic

A tenant whose credentials are overdue SHALL be blocked from accepting new tenant traffic, not only admin operations. Active break-glass grants SHALL be the only override and SHALL be recorded in the audit trail.

The block SHALL apply at webhook acceptance, public API entry points that enqueue or mutate tenant work, and queue enqueue requests. Evaluation SHALL occur after tenant resolution and DPA acknowledgement, and before idempotency records or queue entries are committed. The block SHALL be tenant and credential-scope specific so an overdue GitHub credential does not incorrectly block unrelated read-only administrative status endpoints.

Accepted traffic under break-glass SHALL record `grant_id`, `grant_scope`, `expires_at`, `approved_by`, `second_approved_by`, and `reason` in the run audit trail. Break-glass grants SHALL NOT bypass HMAC verification, IP allowlist checks, DPA acknowledgement, rate limits, or recovery-profile closure.

#### Scenario: Overdue tenant cannot enqueue work
- **WHEN** a tenant credential is overdue and no break-glass grant is active
- **THEN** webhook acceptance, public API entry points, and queue enqueue requests for that tenant are rejected with reason `credential_rotation_overdue`

#### Scenario: Break-glass grant is single-use auditable
- **WHEN** a break-glass grant is active for the tenant
- **THEN** tenant traffic is accepted
- **AND** every accepted run records the grant identifier and expiration

#### Scenario: Expired break-glass grant cannot override rotation block
- **WHEN** the only break-glass grant for an overdue credential is expired
- **THEN** tenant traffic is rejected with reason `credential_rotation_overdue`
- **AND** the rejection audit row includes the expired grant identifier

### Requirement: Profile Drift Detection Alerts On Unsafe Combinations

A periodic job SHALL record the active deployment profile, database driver, and secret backend. The system SHALL alert when a non-`local` profile uses the in-memory database driver or the environment-only secret backend.

The drift job SHALL also record Redis driver, migration state, model catalog source, and webhook acceptance mode. Unsafe combinations include non-`local` memory database driver, non-`local` in-memory queue or Redis replacement, environment-only secret backend, missing KEK reference, missing signing key reference, `recovery` profile with webhook acceptance open, and `air_gapped` profile configured with vendor-hosted secret, model, telemetry, or signing dependencies.

#### Scenario: Unsafe combination in production fires alert
- **WHEN** the periodic check observes `profile=production` and `db_driver=memory`
- **THEN** the alert fires with the offending sample
- **AND** the alert label points to the boot-safety runbook

#### Scenario: Recovery profile with webhooks open fires alert
- **WHEN** the periodic check observes `profile=recovery` and `webhook_acceptance=open`
- **THEN** the alert fires with reason `recovery_webhook_acceptance_open`
- **AND** operators are instructed to close webhook ingress before continuing recovery
