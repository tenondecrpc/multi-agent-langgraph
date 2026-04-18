# Design: Billing Rate-Card Reconciliation

## Context

The active persistence change delivers durable metering and hourly rollups with CSV export. PLAN.md expects rate-card reconciliation against provider invoices. This change builds on the rollups rather than replacing them.

## Goals / Non-Goals

### Goals

- Versioned rate cards with effective windows.
- Cross-reference `provider_request_id` to invoice line items.
- Nightly reconciliation with drift alert at >2%.
- Finance-facing export endpoints under `/api/v1/billing/export`.

### Non-Goals

- No replacement for hourly rollups; they remain the source for CSV export.
- No automatic ingestion of provider invoices; ingestion is operator-driven.

## Decisions

### Decision: Versioned rate cards with shadow mode

A rate-card change is shadow-validated against a recent window of usage before activation to catch drift introduced by the change itself. Activation is audited.

### Decision: Nightly reconciliation ARQ job

The job pulls the day's usage, computes per-provider totals, compares against operator-uploaded invoice line items keyed by `provider_request_id`, and writes a reconciliation row with drift percentage. Drift >2% alerts the finance rotation.

### Decision: Finance export endpoints

`/api/v1/billing/export?version=v1&from=...&to=...` returns CSV; `/api/v1/billing/export?version=v2` returns a finance-friendly JSON with rate-card versioning. Versioning follows the `api-versioning-and-openapi-diff-gate` change.

## Risks / Trade-offs

- Historical rows lacking `provider_request_id`. Mitigated by documented best-effort backfill and clearly reduced-confidence indicator.
- Drift false positives when provider invoice arrives late. Mitigated by reconciliation window and retry cadence.

## Migration Plan

1. Add `provider_request_id` column; start capturing on new rows.
2. Introduce `price_rate_cards`; seed from current rate catalog.
3. Ship reconciliation job in dry-run mode; publish reports.
4. Flip to alerting at >2%.
5. Ship finance export endpoints under API versioning.
