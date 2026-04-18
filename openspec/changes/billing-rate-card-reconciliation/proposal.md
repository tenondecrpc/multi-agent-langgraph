## Why

Tier 2 goal "Billing export" targets hourly rollups plus rate-card reconciliation; the allowed GA degradation is hourly rollups and CSV export only. The active persistence change delivers the degradation; this change lifts the capability to the full goal: versioned `price_rate_cards`, a nightly reconciliation job against provider invoices with a >2% drift alert, `provider_request_id` cross-reference on every `llm_usage` row, and billing export endpoints for finance or ERP ingestion.

## What Changes

- Add `price_rate_cards` with `provider`, `model`, `unit`, `rate_usd`, `effective_from`, `effective_to`, version, and actor metadata.
- Add `provider_request_id` to `llm_usage` for invoice cross-reference; backfill best-effort for historical rows.
- Implement a nightly reconciliation ARQ job that compares `SUM(cost_usd)` from `llm_usage` against provider invoice line items; alert on drift greater than 2%.
- Implement `/api/v1/billing/export` endpoints for finance or ERP ingestion in versioned formats.
- Admin UI rate-card editor with shadow-mode validation before activation.

## Capabilities

### New Capabilities

- `billing-rate-card-and-reconciliation`: rate-card lifecycle, reconciliation job, finance export endpoints.

### Modified Capabilities

- `llm-metering-and-billing`: adds `provider_request_id`, reconciliation integration, and finance export contract.

## Impact

- Code: new `backend/src/backend/governance/billing.py` surface; ARQ scheduled job.
- Schema: `price_rate_cards`, add `provider_request_id` column on `llm_usage`.
- Observability: drift metric, reconciliation-run success, export-call counts.
- Docs: finance integration guide under `docs/`.
- Constitution alignment: Tier 2 goal path; degradation remains documented; no Tier 1 rule affected.
