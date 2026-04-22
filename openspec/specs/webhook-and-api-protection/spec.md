# webhook-and-api-protection Specification

## Purpose
TBD - created by archiving change phase-3-tenant-security-and-access. Update Purpose after archive.
## Requirements
### Requirement: Webhook Authenticity And Freshness Checks

Webhook intake MUST verify authenticity and freshness before work is enqueued.

#### Scenario: Invalid signature is rejected
- **WHEN** an incoming webhook fails HMAC verification
- **THEN** the request is rejected before queueing
- **AND** the rejection is logged as a security event rather than treated as an ordinary ticket failure

#### Scenario: Stale webhook is rejected
- **WHEN** a signed webhook arrives outside the allowed timestamp freshness window
- **THEN** the request is rejected as stale
- **AND** the event does not enter normal processing or idempotency as if it were current

### Requirement: Idempotency And Flood Protection Are Mandatory

Webhook and relevant API surfaces MUST defend against duplicates and abusive request bursts.

#### Scenario: Duplicate webhook is deduplicated
- **WHEN** the same accepted webhook event is received again within the idempotency window
- **THEN** the platform returns a deduplicated success response
- **AND** it does not enqueue a second run for the same event

#### Scenario: Request flood is throttled
- **WHEN** a ticket or endpoint exceeds the configured request rate
- **THEN** the platform throttles the request with rate-limit metadata
- **AND** it preserves platform fairness rather than allowing unbounded intake amplification

### Requirement: Request Rejections Remain Observable

Security and rate-limit rejections MUST remain visible to operators without counting as ordinary service availability failures.

#### Scenario: Security rejection remains auditable
- **WHEN** a webhook is rejected for signature, freshness, or allowlist reasons
- **THEN** the platform records the reason for operator review
- **AND** later observability phases may track those rejections separately from successful intake availability SLIs

### Requirement: Webhook Idempotency Is Durable In PostgreSQL With A Redis Short-Window Cache

Webhook idempotency SHALL be enforced by a `webhook_idempotency_records` table in PostgreSQL with a unique constraint on `(source, delivery_id)`. A Redis short-window cache with TTL equal to the freshness window SHALL absorb burst traffic without hitting PostgreSQL on every call.

#### Scenario: Duplicate delivery is rejected once on the cache and once at the database
- **WHEN** a duplicate webhook arrives inside the freshness window
- **THEN** the Redis cache rejects it with an idempotency error
- **AND** even if the cache missed, the PostgreSQL unique constraint rejects it on insert

#### Scenario: Replay outside the freshness window is rejected by HMAC freshness, not idempotency
- **WHEN** a replay arrives outside the freshness window
- **THEN** HMAC freshness checks reject it before idempotency is consulted
- **AND** the existing webhook security posture is unchanged

### Requirement: Idempotency Records Retain Tenant And Delivery Metadata

Every `webhook_idempotency_records` row SHALL capture `source`, `delivery_id`, `tenant_id`, `team_id`, HMAC digest, `received_at`, and disposition status for audit.

#### Scenario: Audit trail answers "did we already process this"
- **WHEN** an operator investigates a webhook incident
- **THEN** the record is retrievable from PostgreSQL with full metadata
- **AND** retention complies with the data-retention policy

