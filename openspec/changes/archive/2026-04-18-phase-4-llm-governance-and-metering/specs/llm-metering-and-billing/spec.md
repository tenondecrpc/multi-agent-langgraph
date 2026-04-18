## Non-Goals

- Defining frontend chart appearance.
- Defining provider SDK request syntax.
- Defining tenant auth or queue fairness.

## ADDED Requirements

### Requirement: Every LLM Call Is Metered With Full Attribution

Each model invocation MUST record enough attribution to support operational analysis, budgeting, and billing.

#### Scenario: Usage record captures operational dimensions
- **WHEN** a model invocation completes or settles
- **THEN** the usage record includes tenant, team, ticket, role, provider, model, token counts, latency, and cost attribution
- **AND** the record remains linkable to the responsible run or trace context

### Requirement: Billing Uses Stable Rollups And Exports

Billing consumers MUST rely on controlled rollups or export surfaces rather than direct queries against live operational tables.

#### Scenario: Hourly rollup is reproducible
- **WHEN** metering data is aggregated for billing
- **THEN** hourly rollups are created using a stable grouping contract
- **AND** closed periods can be sealed so later billing calculations remain reproducible

#### Scenario: Export surface supports finance ingestion
- **WHEN** finance or ERP systems request usage data
- **THEN** the platform provides a bounded export contract such as CSV or JSONL
- **AND** the billing consumer does not need unrestricted access to operational metering tables

### Requirement: Rate Cards And Reconciliation Are Versioned

Billing calculations MUST use versioned rate cards and MUST support reconciliation against provider invoices or usage statements.

#### Scenario: Historical usage uses the active rate card at usage time
- **WHEN** historical billing is recomputed
- **THEN** each usage record resolves against the rate card that was active when the usage occurred
- **AND** later pricing changes do not silently rewrite prior invoices

#### Scenario: Reconciliation drift is observable
- **WHEN** provider invoice totals materially diverge from metered usage totals
- **THEN** the platform can detect and surface the drift for investigation
- **AND** billing discrepancies do not remain invisible to operators

### Requirement: CSV-Only Export Is An Allowed Tier 2 Degradation

The platform MUST preserve a documented Tier 2 degradation path in which hourly rollups and CSV export ship before full automated reconciliation.

#### Scenario: Early GA ships reduced billing scope
- **WHEN** the product ships the allowed Tier 2 billing degradation path
- **THEN** hourly rollups and CSV export remain available
- **AND** the lack of automated reconciliation is recorded as a parity gap rather than an unplanned omission
