# Design: Data Retention, Deletion, And DPA Compliance

## Context

Phase 7 defined retention and GDPR direction; PLAN.md adds concrete jobs and a DPA gate. Without enforcement and tenant-delete cascade, the product cannot accept real customer data.

## Goals / Non-Goals

### Goals

- Enforced retention with partition drops and auditable row-deletion counts.
- Tenant-delete that is complete and verifiable.
- DPA gate that blocks processing until the current version is acknowledged per tenant.

### Non-Goals

- No cross-customer deletion workflows (there is no cross-customer data plane).
- No change to observability-log retention beyond documenting it.

## Decisions

### Decision: Retention via partitioned drops where possible

`metering_facts` is partitioned by month; retention drops whole partitions instead of row-by-row delete. Checkpoints and memory use keyed TTL deletes in batches with bounded lock windows. DLQ expiry deletes rows older than policy with audit rows recorded.

### Decision: Tenant delete is a staged workflow

Tenant delete records a `tenant_delete_events` row with `requested_by`, `approved_by`, `reason`. A super_admin approval step precedes cascade execution. Cascade runs in dependency order and emits per-table deletion counts. Audit rows are pseudonymized (actor hashed) rather than deleted to preserve tamper-evident history while respecting erasure intent.

### Decision: DPA gate middleware

A FastAPI middleware blocks ticket acceptance when the tenant has not acknowledged the current DPA version. DPA versions are stored with `version`, `published_at`, `content_hash`. Acknowledgements record `tenant_id`, `acknowledger`, `acknowledged_at`, `dpa_version`. Re-prompting happens on version change.

## Risks / Trade-offs

- Partition drop under load. Mitigated by running retention jobs during low-traffic windows and reporting durations.
- Pseudonymization vs deletion in audit. Documented as a deliberate tradeoff aligned with GDPR guidance for tamper-evident logs.
- DPA version churn. Mitigated by rare publication and grace period.

## Migration Plan

1. Partition `metering_facts` by month via expand/contract migration; retain existing rows during transition.
2. Ship retention CronJobs in dry-run mode; compare row counts.
3. Flip to enforce; monitor deletion counts.
4. Introduce DPA table and gate middleware with a 30-day grace period, then enforce.
5. Add tenant-delete admin UI; require dual-control approval for production.
