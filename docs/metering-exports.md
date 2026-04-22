# Metering Exports

This repository now supports durable metering facts in PostgreSQL and hourly rollups used for CSV export.

## Current production posture

- Raw LLM usage facts are stored in the `metering_facts` table.
- Hourly aggregates are materialized into `metering_hourly_rollups`.
- CSV export reads from `metering_hourly_rollups`, not directly from raw facts.

## Tier 2 degradation note

The current export path intentionally implements the allowed Tier 2 degradation described in `docs/PLAN.md`:

- hourly rollups are durable and exportable
- CSV export is available from rollups
- full rate-card lifecycle and reconciliation are deferred

The deferred parity work is tracked in:

- `openspec/changes/billing-rate-card-reconciliation`

## Backfill and replay

- Hourly rollups are built idempotently from `metering_facts`
- Re-running a rollup window replaces the prior aggregate for the same rollup key
- This supports backfill after outages or delayed ingestion
