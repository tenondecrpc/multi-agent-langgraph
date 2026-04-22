# Persistence Backup And Restore

- PostgreSQL backups cover `runs`, `webhook_idempotency_records`, `graph_versions`, `agent_versions`, `snapshots`, `run_snapshot_bindings`, `shadow_reports`, `audit_events`, `dead_letter_records`, `budget_cap_snapshots`, `budget_reservations`, `budget_charges`, `budget_denials`, `metering_facts`, `metering_facts_default`, `metering_hourly_rollups`, `model_catalog_entries`, `role_token_policies`, and `provider_health_events`.
- Redis recovery depends on PostgreSQL-backed reconciliation for budget counters, provider health audit evidence, and worker drain state. Treat Redis as reconstructible, not authoritative.
- RPO target: 15 minutes. RTO target: 45 minutes.
- Quarterly drill evidence is stored in `docs/drills/2026-q2-persistence-drill.md`.

## Restore Checklist

1. Restore PostgreSQL from the latest base backup plus WAL.
2. Run `alembic upgrade head` and confirm the revision matches `/metrics`.
3. Replay the persistence smoke suite and the runtime E2E smoke path.
4. Reconcile Redis-backed counters from PostgreSQL before opening ingress.
5. Confirm `/readyz` stays green and provider circuit breakers are closed.
