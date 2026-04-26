## ADDED Requirements

### Requirement: Versioned Rate Cards With Effective Windows

The backend SHALL maintain a `price_rate_cards` table with `provider`, `model`, `unit`, `rate_usd`, `effective_from`, `effective_to`, version, and actor metadata. Rate-card changes SHALL be audited and SHALL pass shadow-mode validation before activation.

#### Scenario: Shadow validation catches regression
- **WHEN** a rate-card change produces excessive variance against recent usage
- **THEN** activation is blocked
- **AND** the reviewer sees the comparison evidence

### Requirement: Cross-Reference Provider Request Id On Usage Rows

Every `llm_usage` row SHALL carry a `provider_request_id` when the provider exposes one. The reconciliation job SHALL use this identifier to match invoice line items.

#### Scenario: Missing id on historical row is indicated
- **WHEN** reconciliation encounters a row without `provider_request_id`
- **THEN** the row is excluded from strict matching
- **AND** the exclusion count is visible on the reconciliation report

### Requirement: Nightly Reconciliation With Drift Alert

A nightly ARQ job SHALL reconcile `SUM(cost_usd)` against provider invoice line items and SHALL alert when drift exceeds 2 percent.

#### Scenario: Drift exceeds threshold
- **WHEN** drift is greater than 2 percent for a provider in a day
- **THEN** an alert routes to the finance rotation
- **AND** the report is retrievable under `docs/quality/` or equivalent retention surface

### Requirement: Finance Export Endpoints Under API Versioning

The backend SHALL expose `/api/v1/billing/export` endpoints returning CSV and a finance-friendly JSON version. Both SHALL respect the API-versioning contract including deprecation headers.

#### Scenario: v1 CSV export is stable under v2
- **WHEN** v2 JSON export ships
- **THEN** v1 CSV export continues to produce for at least 12 months
