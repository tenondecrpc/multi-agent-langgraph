## Why

The constitution requires data retention, deletion, and DPA acknowledgement. PLAN.md specifies retention CronJob enforcement (partition drop for metering, checkpoint cleanup, memory TTL, DLQ expiry), tenant-delete cascade, audit-log pseudonymization, DPA acknowledgment gate that blocks ticket processing, and a GDPR erasure runbook. Phase 7 covered the strategy; this change wires the enforcement and the DPA gate.

## What Changes

- Retention enforcement CronJob(s): partition drop for `metering_facts`, checkpoint cleanup outside retention, long-term memory TTL eviction, DLQ expiry per policy.
- Tenant-delete cascade: hard-delete configs, checkpoints, memory, metering, sessions, credentials, sprites; pseudonymize audit-log actor references where retention mandates keep the event but not the identity.
- DPA acknowledgement gate: block ticket processing per tenant until the customer super_admin has acknowledged the current provider DPA; version the DPA and re-prompt on changes.
- GDPR erasure runbook with defined RPO and RTO for erasure requests and end-to-end audit evidence.

## Capabilities

### New Capabilities

- `data-retention-deletion-and-dpa`: contract for retention CronJobs, tenant-delete cascade, audit pseudonymization, DPA gate, GDPR erasure runbook.

### Modified Capabilities

- `data-retention-and-compliance-operations`: wires the specific jobs, the cascade definition, and the DPA gate.

## Impact

- Code: `backend/src/backend/operations/retention.py` (jobs), admin UI tenant-delete flow, DPA acknowledgement endpoints and gate middleware.
- Schema: `dpa_versions`, `dpa_acknowledgements`, `tenant_delete_events`.
- Observability: retention-run success, rows-deleted counts, DPA-block counts.
- Docs: `docs/` GDPR erasure runbook and DPA publication workflow.
- Constitution alignment: Tier 1 preserved.
