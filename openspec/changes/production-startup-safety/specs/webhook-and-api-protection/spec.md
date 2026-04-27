## ADDED Requirements

### Requirement: Webhook Path Enforces Credential Rotation, Break-Glass, And DPA

Webhook acceptance SHALL evaluate, in order: IP allowlist (PostgreSQL-backed), HMAC signature with rotation overlap, tenant DPA acknowledgement, tenant credential rotation status, idempotency, and rate limits. Each rejection SHALL write a structured reason code to the existing webhook rejection audit.

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

### Requirement: Webhook IP Allowlist Lives In Versioned PostgreSQL Config

The webhook IP allowlist SHALL live in PostgreSQL versioned config. Environment-based fallback SHALL apply only during a documented cutover stage, and a drift alert SHALL fire whenever the two sources disagree.

#### Scenario: PostgreSQL value wins after cutover
- **WHEN** the cutover stage advances to PostgreSQL-authoritative
- **THEN** environment-based values are ignored
- **AND** any operator change to the allowlist is auditable through the existing config audit trail
