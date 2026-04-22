## ADDED Requirements

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
