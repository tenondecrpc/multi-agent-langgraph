# Operations Runbook

## Severity Levels

- `sev1`: customer-visible outage or data-plane loss with immediate paging
- `sev2`: serious degradation with customer impact and urgent operator response
- `sev3`: limited degradation with planned remediation
- `sev4`: low-risk operational issue or hygiene task

## Pager-Worthy Alerts

- API burn-rate critical alert
- Worker queue backlog exhaustion
- Provider failover exhaustion
- Checkpoint durability regression

Every pager-worthy alert must reference a runbook identifier in the operational catalog and a component-level public status update path when customers are affected.

## Schema Migrations

- Alembic commands and startup-migration guidance live in [persistence-migrations.md](/Users/tenonde/Projects/personal/multi-agent-langgraph/docs/persistence-migrations.md:1).
- `BACKEND_AIR_GAPPED_SKIP_MIGRATIONS=1` is the kill switch for air-gapped pre-seeded databases.
- Treat every database migration as a high-risk rollout item and record operator rationale for any waiver.

## Drill Evidence Checklist

- Backup identifier and verification timestamp
- Restore drill outcome and measured RPO/RTO
- Rollback drill outcome and rollback duration
- Snapshot retention checks for active and paused runs
- Recorded operator rationale for any override or waiver

## Persistence-Specific Runbooks

- `persistence-dlq-growth` - investigate `dead_letter_records`, checkpoint refs, and queue starvation.
- `persistence-breaker-open` - verify provider-health events, half-open recovery, and fail-closed posture in air-gapped mode.
- `persistence-dr` - restore PostgreSQL, repopulate Redis coordination state from durable rows, and validate readiness before traffic.
