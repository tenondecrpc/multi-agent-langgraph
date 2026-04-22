## ADDED Requirements

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
