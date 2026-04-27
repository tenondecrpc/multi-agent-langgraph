## ADDED Requirements

### Requirement: Webhook Path Enforces Credential Rotation, Break-Glass, And DPA

Webhook acceptance SHALL evaluate, in order: IP allowlist (PostgreSQL-backed), HMAC signature with rotation overlap, tenant DPA acknowledgement, tenant credential rotation status, idempotency, and rate limits. Each rejection SHALL write a structured reason code to the existing webhook rejection audit.

Webhook acceptance SHALL use the following ordered gates:

1. Runtime profile gate. `recovery` rejects all webhook traffic with `recovery_profile_active`.
2. PostgreSQL-backed IP allowlist, using cutover semantics from the versioned config entity.
3. HMAC signature verification with timestamp freshness and rotation overlap.
4. Tenant resolution and active tenant/team authorization.
5. Current DPA acknowledgement.
6. Credential rotation status, with break-glass checked only as a scoped override for overdue credentials.
7. Idempotency.
8. Rate limit and weighted-fair enqueue guard.

Required rejection reason codes are `recovery_profile_active`, `ip_not_allowed`, `signature_invalid`, `signature_stale`, `tenant_unknown`, `tenant_disabled`, `dpa_acknowledgement_required`, `credential_rotation_overdue`, `break_glass_grant_invalid`, `duplicate_delivery`, `rate_limited`, and `queue_unavailable`. Rejections SHALL write an audit row with `source`, `delivery_id`, `tenant_id` when known, `team_id` when known, `reason`, `profile`, `client_ip_hash`, `signature_key_id` when available, `dpa_version_required` when applicable, `credential_id` when applicable, `break_glass_grant_id` when applicable, `received_at`, and `runbook_url`.

#### Scenario: Overdue credential blocks webhook
- **WHEN** a tenant has an overdue credential without an active break-glass grant
- **THEN** the webhook is rejected with reason `credential_rotation_overdue`
- **AND** the rejection is auditable

#### Scenario: Break-glass grant overrides block
- **WHEN** an active break-glass grant covers the overdue credential
- **THEN** the webhook is accepted
- **AND** the run audit records the break-glass grant identifier

#### Scenario: Missing DPA blocks webhook
- **WHEN** the tenant has not acknowledged the current DPA version
- **THEN** the webhook is rejected with reason `dpa_acknowledgement_required`

#### Scenario: Recovery profile rejects before idempotency
- **WHEN** a webhook arrives while `BACKEND_DEPLOYMENT_PROFILE=recovery`
- **THEN** the request is rejected with reason `recovery_profile_active`
- **AND** no idempotency record or queue entry is created

#### Scenario: Break-glass does not bypass DPA
- **WHEN** a tenant has an active break-glass grant but has not acknowledged the current DPA version
- **THEN** the webhook is rejected with reason `dpa_acknowledgement_required`
- **AND** the break-glass grant is not consumed or recorded as authorizing the run

### Requirement: Webhook IP Allowlist Lives In Versioned PostgreSQL Config

The webhook IP allowlist SHALL live in PostgreSQL versioned config. Environment-based fallback SHALL apply only during a documented cutover stage, and a drift alert SHALL fire whenever the two sources disagree.

The versioned config entity SHALL be named `webhook_ip_allowlist`. Each version SHALL include `tenant_id`, optional `team_id`, `source`, `cidrs`, `mode`, `description`, `created_by`, `reviewed_by`, `activated_by`, `created_at`, `activated_at`, `expires_at` when temporary, `previous_version_id`, `change_reason`, and `shadow_validation_result`. Values SHALL be audited through the existing config audit trail and SHALL be compatible with rollback to a previous config version.

Cutover SHALL run in two stages:

- Stage 1, `shadow_env_fallback`: PostgreSQL is read first. If no PostgreSQL value exists for the tenant, environment values MAY be used. Writes go only to PostgreSQL. Drift between PostgreSQL and environment values increments `devsquad_ip_allowlist_drift_total{tenant}` and writes an audit row.
- Stage 2, `postgres_authoritative`: PostgreSQL is authoritative. Environment values are ignored for enforcement and may only be retained as rollback input until the rollback window closes.

Rollback to environment values SHALL require an explicit operator action, a reason, and an audit row. Rollback SHALL be allowed only during the configured cutover window, SHALL set cutover mode back to `shadow_env_fallback`, and SHALL fire a warning alert. After the rollback window closes, rollback SHALL use previous PostgreSQL config versions rather than environment values.

#### Scenario: PostgreSQL value wins after cutover
- **WHEN** the cutover stage advances to PostgreSQL-authoritative
- **THEN** environment-based values are ignored
- **AND** any operator change to the allowlist is auditable through the existing config audit trail

#### Scenario: Stage 1 drift alerts
- **WHEN** PostgreSQL and environment allowlists differ during `shadow_env_fallback`
- **THEN** the drift alert fires with tenant and source metadata
- **AND** enforcement still follows the documented stage 1 precedence

#### Scenario: Environment rollback is time-bound
- **WHEN** an operator rolls back to environment values during the cutover window
- **THEN** the rollback writes an audit row with actor, reason, previous config version, and expiry
- **AND** a warning alert remains active until PostgreSQL authoritative mode is restored

### Requirement: Webhook Startup Safety Emits Metrics And Alerts

Webhook and profile safety enforcement SHALL emit metrics and alerts for boot failures, readiness failures, webhook rejections, credential-rotation blocks, break-glass usage, DPA blocks, IP allowlist drift, and profile drift.

Required metrics are:

- `devsquad_boot_failures_total{profile,reason}`.
- `devsquad_readiness_failures_total{profile,reason}`.
- `devsquad_webhook_rejections_total{profile,reason,source}`.
- `devsquad_credential_rotation_block_webhook_total{tenant,credential_type}`.
- `devsquad_break_glass_webhook_acceptances_total{tenant,grant_scope}`.
- `devsquad_dpa_webhook_blocks_total{tenant,dpa_version}`.
- `devsquad_ip_allowlist_drift_total{tenant}`.
- `devsquad_deployment_profile_drift_total{profile,reason}`.

Alerts SHALL cover non-local in-memory adapters, non-local env-only secret backend, recovery profile accepting webhooks, boot failure loops, readiness `not_configured` in non-local profiles, credential rotation webhook blocks above threshold, DPA webhook blocks above threshold, and IP allowlist drift. Every alert SHALL include a runbook reference and the active runtime profile.

#### Scenario: Readiness not configured in production alerts
- **WHEN** `/readyz` reports `not_configured` in `production`
- **THEN** `devsquad_readiness_failures_total{profile="production",reason="not_configured"}` increments
- **AND** an alert links the startup safety runbook

### Requirement: Webhook Safety Implementation Is Deferred Until Specification Completion

Implementation of webhook gate ordering, versioned IP allowlist migration, cutover rollback, and webhook safety metrics SHALL be deferred to a follow-up OpenSpec apply pass after this specification phase is complete. The follow-up implementation SHALL include tests for every rejection reason, both cutover stages, and recovery-profile closure.

#### Scenario: Specification phase completes without webhook code
- **WHEN** this OpenSpec change completes its artifact tasks
- **THEN** it may mark specification tasks complete without changing webhook runtime code
- **AND** the next apply pass must implement the webhook gates before production readiness claims are made
