# Runbook: Persistence Disaster Recovery

## Targets

- RPO: 4 hours
- RTO: 30 minutes for control plane and runtime intake

## Restore Order

1. Restore PostgreSQL to the latest valid snapshot plus WAL replay.
2. Recreate Kubernetes secrets through Vault and External Secrets Operator.
3. Restart backend pods and confirm Alembic revision equals the chart target.
4. Rebuild Redis coordination state by running ledger reconciliation and drain-lease cleanup.
5. Verify `/readyz` returns `ok` with an active snapshot id before reopening traffic.

## Evidence

- Backup identifier
- Restore timestamp
- Observed RPO/RTO
- Operator sign-off
