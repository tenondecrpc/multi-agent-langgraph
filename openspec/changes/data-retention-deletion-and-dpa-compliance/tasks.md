## 1. Artifact Alignment

- [ ] 1.1 Confirm composition with Phase 7 retention and compliance specs and with the active persistence change (metering partitioning and DLQ tables).

## 2. Retention Jobs

- [ ] 2.1 Partition `metering_facts` by month via expand/contract; document reversibility.
- [ ] 2.2 Implement retention CronJobs: metering partition drop, checkpoint cleanup, memory TTL, DLQ expiry.
- [ ] 2.3 Dry-run mode first; compare row counts; flip to enforce.

## 3. Tenant Delete

- [ ] 3.1 `tenant_delete_events` table and dual-control approval endpoints.
- [ ] 3.2 Cascade implementation with per-table counts and audit pseudonymization.
- [ ] 3.3 Admin UI flow with accessibility non-negotiable subset verified.

## 4. DPA Gate

- [ ] 4.1 `dpa_versions` and `dpa_acknowledgements` tables; publication workflow.
- [ ] 4.2 FastAPI middleware blocks ticket acceptance until acknowledged.
- [ ] 4.3 Grace-window handling on new version publication.

## 5. Docs

- [ ] 5.1 GDPR erasure runbook under `docs/` with RPO and RTO.
- [ ] 5.2 DPA publication workflow and version-change operator guide.

## 6. Observability

- [ ] 6.1 Metrics: retention-run success, rows-deleted, DPA-block counts, erasure duration.
- [ ] 6.2 Alerts for job failure and for long-outstanding erasure requests.

## 7. Verification

- [ ] 7.1 `uv run --project backend pytest` including cascade integration test.
- [ ] 7.2 Air-gapped dry-run evidence attached.

## 8. Archive

- [ ] 8.1 Archive after one full retention cycle and one erasure drill in staging.
