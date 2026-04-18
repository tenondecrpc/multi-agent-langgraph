# Design: Jira Webhook Replay And Rate-Limit Hardening

## Context

Webhooks are the only external entry point for ticket work. Missing defenses against header-replay, burst flooding, and inadequate secret rotation would let a malicious actor bypass idempotency or cause fair-queue starvation. This change assumes the active persistence backbone is in place (durable idempotency table, Redis available for sliding-window counters).

## Goals / Non-Goals

### Goals

- Rotating HMAC secrets with a 24-hour overlap.
- Per-ticket flood limit enforced across replicas.
- Optional per-tenant source-IP allowlist evaluated before signature verification.
- Idempotency keyed on content integrity (signature hash) as well as delivery id.

### Non-Goals

- No change to the ticket pipeline graph or to the webhook HMAC algorithm family.
- No vendor-hosted WAF. All enforcement runs inside the customer-owned cluster.

## Decisions

### Decision: Two-secret rotation window

Each tenant has `current_secret` and optional `previous_secret` valid until `rotation_overlap_until`. The verifier accepts a signature that matches either secret during the overlap window; outside the overlap, only `current_secret` is accepted. Rotation is an audited super_admin action.

### Decision: Redis sliding-window counter keyed per ticket

The per-ticket flood limit uses a Redis sorted set keyed by `ticket_key` with a one-minute sliding window. A Lua script atomically adds the current timestamp, trims entries older than 60 seconds, and returns the count. Over-limit requests respond `429` and emit a `webhook_rate_limit_rejections` audit row.

### Decision: IP allowlist is a cheap pre-filter

When set, the allowlist is evaluated before signature verification to avoid consuming HMAC compute on denied traffic. Rejections are logged at a per-IP rate cap to prevent log floods.

### Decision: Content-integrity idempotency key

Idempotency becomes `(source, delivery_id, signature_hash)`. Replays that mutate headers but keep the body unchanged still collide on the unique constraint; replays that mutate the body change `signature_hash` and therefore fail HMAC verification first. This closes the header-replay gap.

## Risks / Trade-offs

- Slightly larger idempotency index. Mitigated by composite index design.
- Clock skew during secret rotation. Mitigated by generous overlap and alerting if `previous_secret` expires unused.
- Misconfigured IP allowlist could lock out legitimate Jira traffic. Mitigated by dry-run mode, operator preview, and "allow-any" default.

## Migration Plan

1. Expand schema: add `signature_hash` column, backfill with NULL, switch new inserts to include it, change unique index to a composite index including `signature_hash` once backfill completes.
2. Ship rotation infrastructure behind a feature flag; rotate a canary tenant, then expand.
3. Enable per-ticket flood limit in shadow mode; then enforce.
4. Enable optional IP allowlist configuration in admin UI; default remains "allow any".
