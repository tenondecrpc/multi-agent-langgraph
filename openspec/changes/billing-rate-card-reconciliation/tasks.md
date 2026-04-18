## 1. Artifact Alignment

- [ ] 1.1 Compose with the active persistence change (metering and rollups) and `api-versioning-and-openapi-diff-gate`.

## 2. Schema

- [ ] 2.1 Add `price_rate_cards`; seed from current catalog.
- [ ] 2.2 Add `provider_request_id` to `llm_usage`; best-effort backfill.

## 3. Rate-Card Lifecycle

- [ ] 3.1 Admin UI rate-card editor with shadow-mode validation.
- [ ] 3.2 Audit on activation; versioned effective windows.

## 4. Reconciliation

- [ ] 4.1 Nightly ARQ reconciliation job; dry-run mode first.
- [ ] 4.2 Drift alert at >2 percent routed to finance rotation.

## 5. Finance Export

- [ ] 5.1 Implement `/api/v1/billing/export` CSV and JSON versions.
- [ ] 5.2 Respect deprecation headers and versioning lifecycle.

## 6. Observability

- [ ] 6.1 Metrics: drift percentage per provider, reconciliation duration, export-call counts, missing-id counts.
- [ ] 6.2 Runbook for drift investigation.

## 7. Verification

- [ ] 7.1 `uv run --project backend pytest`.
- [ ] 7.2 End-to-end reconciliation dry-run in staging with synthetic invoices.

## 8. Archive

- [ ] 8.1 Archive after one successful production reconciliation cycle.
