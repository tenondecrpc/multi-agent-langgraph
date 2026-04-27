# tenant-isolation-and-credentials Specification

## Purpose
TBD - created by archiving change phase-3-tenant-security-and-access. Update Purpose after archive.
## Requirements
### Requirement: Tenant And Team Isolation Boundaries

The product MUST enforce tenant and team isolation across repository scope, credentials, data visibility, memory, and budget ownership.

#### Scenario: Repository scope stays team-bound
- **WHEN** a run is created for a team
- **THEN** repository access is limited to the repositories allowed for that team
- **AND** the run cannot expand its repository scope by reading or writing another team's repositories

#### Scenario: Visibility stays tenant-scoped
- **WHEN** users query jobs, metrics, or streams
- **THEN** they only receive data for their tenant and authorized teams
- **AND** cross-tenant visibility is reserved only for explicit super-admin operational surfaces

### Requirement: Credentials Are Service-Layer Secrets

Credentials MUST remain service-layer material, never part of the LLM context, and MUST be isolated per team or stronger boundary.

#### Scenario: Runtime retrieves credentials without exposing them to the model
- **WHEN** the service resolves GitHub, Jira, or provider credentials for a run
- **THEN** those secrets are accessed by the service and tool layers only
- **AND** they are not inserted into prompts, model context, frontend bundles, or logs

#### Scenario: Credential scope remains team-specific
- **WHEN** multiple teams operate within the same tenant deployment
- **THEN** each team uses its own credential set or stricter boundary
- **AND** one team's run cannot borrow another team's write credentials

### Requirement: Envelope Encryption And Rotation Are Mandatory

Stored credentials MUST be envelope-encrypted with tenant-scoped key hierarchy and MUST follow a bounded rotation policy.

#### Scenario: Stored credentials remain encrypted at rest
- **WHEN** credential material is persisted in PostgreSQL or delivered to workloads
- **THEN** the credential payload is stored as ciphertext protected by tenant-scoped key material
- **AND** plaintext credentials do not live in committed configuration, ConfigMaps, or long-lived logs

#### Scenario: Overdue rotation blocks new runs
- **WHEN** a credential set passes its allowed rotation window
- **THEN** the system marks the credential set as overdue
- **AND** new runs for that scope may be blocked until rotation is completed or an explicit break-glass procedure is invoked

### Requirement: GitHub App Is The Default Integration Identity

GitHub App installation tokens MUST be the default integration path, while PAT usage remains an explicit and more restricted fallback.

#### Scenario: Standard onboarding uses GitHub App
- **WHEN** a team configures GitHub access for normal operation
- **THEN** the default path uses GitHub App installation tokens minted on demand
- **AND** long-lived PATs are not treated as the preferred baseline

#### Scenario: PAT fallback is clearly constrained
- **WHEN** a tenant cannot use a GitHub App and opts into PAT mode
- **THEN** the tenant is flagged for stricter policy and audit treatment
- **AND** PAT mode does not weaken repository safety or branch-protection checks

### Requirement: GitHub Credentials Flow Through The Onboarding Record

Tenant GitHub credentials (App installation references and opt-in PAT ciphertext) SHALL be stored only through the integration onboarding record. Environment-variable or config-file storage of GitHub credentials is forbidden.

#### Scenario: Direct env-var usage is rejected
- **WHEN** code attempts to read a GitHub token from an environment variable or config file at runtime
- **THEN** a lint rule or startup check fails the build or the pod startup
- **AND** the operator sees a structured error referencing the onboarding surface

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
