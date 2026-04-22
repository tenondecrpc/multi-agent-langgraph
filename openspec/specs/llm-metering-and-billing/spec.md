# llm-metering-and-billing Specification

## Purpose
TBD - created by archiving change phase-4-llm-governance-and-metering. Update Purpose after archive.
## Requirements
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

### Requirement: Metering Facts Are Durable In PostgreSQL And Partitioned By Time

Every metered LLM call SHALL write a fact row to a partitioned PostgreSQL table `metering_facts` keyed by tenant, team, model, provider, run, and timestamp. In-memory metering storage MUST NOT exist in production paths.

#### Scenario: Metering survives restart and replication
- **WHEN** workers restart during a busy period
- **THEN** all prior metering facts remain queryable
- **AND** no facts are reconstructed from in-process memory

### Requirement: Hourly Rollups And CSV Export Are Scheduled Jobs

Hourly rollups SHALL be produced by a scheduled ARQ job that aggregates `metering_facts` into `metering_hourly_rollups`. CSV export SHALL remain the Tier 2 allowed degradation path and SHALL operate from the rollup table, not from raw facts.

#### Scenario: CSV export reconciles with rollups
- **WHEN** an operator requests a CSV export for a time window
- **THEN** the export reads only from `metering_hourly_rollups`
- **AND** row totals match the sum over `metering_facts` within a declared tolerance

