## Why

Phase 3 delivered webhook HMAC, freshness, and basic idempotency. PLAN.md requires a stricter production posture: 24-hour HMAC secret rotation overlap window, per-ticket flood rate limit (20 events/min/ticket), optional per-tenant source-IP allowlist, and signature-hash inclusion in the idempotency key to prevent header-replay bypass. The active persistence change makes idempotency durable; this change completes webhook hardening to meet the Tier 1 webhook-security non-negotiable.

## What Changes

- Rotating HMAC secrets: support two concurrent secrets per tenant with a 24-hour overlap window; reject requests that match neither.
- Per-ticket flood rate limit: cap accepted events at 20 per minute per ticket across all replicas using a Redis sliding-window counter; excess events are rejected with `429` and audit evidence.
- Optional per-tenant source-IP allowlist: CIDR list; when set, requests outside the allowlist are refused before signature verification, with rate-limited log emission.
- Signature-hash in idempotency key: change the idempotency key from `(source, delivery_id)` to `(source, delivery_id, signature_hash)` so a replay with a mutated header cannot bypass the PostgreSQL unique constraint.
- Rate-limit configuration (allowlist, per-tenant caps, freshness window) lives in the versioned PostgreSQL config store; shadow-mode validation on change.

## Capabilities

### Modified Capabilities

- `webhook-and-api-protection`: rotating secrets, per-ticket flood limit, optional IP allowlist, signature-hash idempotency key, config-driven thresholds.

## Impact

- Code: `backend/src/backend/security/webhook.py` and the platform API webhook handler; configuration surface for allowlist and caps.
- Schema: extend `webhook_idempotency_records` with `signature_hash`; add `webhook_secret_rotations` for overlap windows; add `webhook_rate_limit_rejections` for audit.
- Secrets: both current and previous HMAC secrets flow through Vault; rotation overlap is a first-class Vault event.
- Observability: rate-limit rejections, IP-allowlist blocks, secret-rotation overlap status, and freshness-violation counters.
- Tests: chaos tests for secret rotation mid-traffic, fuzz tests on signature validation, integration tests for the flood limit under N-replica load.
- Constitution alignment: Tier 1 preserved; webhook security hardened end-to-end.
