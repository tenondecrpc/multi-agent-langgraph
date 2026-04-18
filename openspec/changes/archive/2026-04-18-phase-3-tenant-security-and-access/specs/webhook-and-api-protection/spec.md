## Non-Goals

- Defining business logic for ticket planning or graph routing.
- Defining CI or image-signing workflow details.
- Defining frontend auth UX.

## ADDED Requirements

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
