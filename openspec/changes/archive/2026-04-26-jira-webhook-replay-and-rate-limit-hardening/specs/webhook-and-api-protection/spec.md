## ADDED Requirements

### Requirement: Rotating HMAC Secrets With Overlap Window

The webhook guard SHALL accept HMAC signatures computed against either the tenant's current secret or its previous secret, when the previous secret is within its rotation overlap window of up to 24 hours. Outside the overlap, only the current secret SHALL be accepted.

#### Scenario: Signature valid under previous secret during overlap
- **WHEN** a request arrives during the overlap window with a signature matching the previous secret
- **THEN** the guard accepts the request
- **AND** emits a metric `webhook_signature_matched_previous` for observability

#### Scenario: Previous secret is rejected after overlap expires
- **WHEN** the overlap window has passed
- **THEN** signatures matching only the previous secret are rejected
- **AND** an audit row is written

### Requirement: Per-Ticket Flood Rate Limit

The webhook guard SHALL reject accepted webhook events that exceed 20 per minute per ticket across all replicas. Rejection SHALL return HTTP 429 and SHALL record a `webhook_rate_limit_rejections` audit row.

#### Scenario: Flood trips the limit
- **WHEN** a ticket receives more than 20 events in any 60-second window
- **THEN** subsequent events within that window are rejected with 429
- **AND** the rejection is observable per tenant and per ticket

### Requirement: Optional Per-Tenant Source-IP Allowlist

The webhook guard SHALL support an optional per-tenant CIDR allowlist. When set, requests from outside the allowlist SHALL be rejected before signature verification.

#### Scenario: Request from outside the allowlist is rejected
- **WHEN** a tenant has a non-empty allowlist and a request originates outside it
- **THEN** the guard responds 403 without consuming HMAC compute
- **AND** logs the rejection at a per-IP rate cap

### Requirement: Idempotency Key Includes Signature Hash

The idempotency key SHALL be `(source, delivery_id, signature_hash)`. Duplicate delivery with a mutated body fails HMAC verification; duplicate delivery with the same body collides on the unique constraint.

#### Scenario: Header-replay attack cannot bypass idempotency
- **WHEN** an attacker replays a request with the same body but different headers
- **THEN** the PostgreSQL unique constraint on `(source, delivery_id, signature_hash)` rejects the duplicate
- **AND** no new ticket run is accepted

### Requirement: Rate-Limit And Allowlist Config Is Versioned

Rate-limit thresholds, allowlist CIDRs, rotation overlap windows, and freshness windows SHALL live in the versioned PostgreSQL config store with shadow-mode validation on change.

#### Scenario: Config change validates in shadow mode
- **WHEN** an operator changes any of these thresholds
- **THEN** the change runs in shadow mode first and produces a comparison report
- **AND** activation requires the report to be non-blocking or overridden by super_admin with audited rationale
