## 1. Artifact Alignment

- [ ] 1.1 Confirm this proposal composes cleanly with the active `replace-in-memory-with-postgres-redis` change; block implementation until that change lands the durable idempotency table.

## 2. Schema And Config

- [ ] 2.1 Expand `webhook_idempotency_records` with `signature_hash`; switch unique index to `(source, delivery_id, signature_hash)` using expand/contract.
- [ ] 2.2 Add `webhook_secret_rotations` and `webhook_rate_limit_rejections` tables with reversibility tests.
- [ ] 2.3 Wire rate-limit thresholds, allowlist CIDRs, and rotation-overlap window into the versioned PostgreSQL config store with shadow-mode validation.

## 3. Rotating Secrets

- [ ] 3.1 Implement dual-secret verifier and Vault-backed rotation endpoint (super_admin).
- [ ] 3.2 Observability: `webhook_signature_matched_previous`, overlap-expiry alert, rotation-overdue alert.
- [ ] 3.3 Chaos test: rotate a tenant mid-traffic; verify zero dropped legitimate requests.

## 4. Per-Ticket Flood Limit

- [ ] 4.1 Implement Redis sliding-window Lua script; return HTTP 429 on excess.
- [ ] 4.2 Shadow-mode release; then enforce.
- [ ] 4.3 Load test with N-replica synthetic burst; verify limit holds across replicas.

## 5. IP Allowlist

- [ ] 5.1 Implement pre-signature allowlist filter with per-IP rate-capped logging.
- [ ] 5.2 Admin UI CIDR editor with validation and dry-run preview; accessibility non-negotiable subset verified.

## 6. Observability

- [ ] 6.1 Metrics and alerts for rejections and rotation status; runbooks under `docs/`.

## 7. Verification

- [ ] 7.1 `uv run --project backend ruff check` and `uv run --project backend pytest` green including fuzz tests on signature validation.
- [ ] 7.2 E2E smoke test: normal webhook path unaffected.

## 8. Archive

- [ ] 8.1 Archive after enforce-mode stable and rotation drill executed once in staging.
