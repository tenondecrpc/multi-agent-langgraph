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

## Drill Evidence Checklist

- Backup identifier and verification timestamp
- Restore drill outcome and measured RPO/RTO
- Rollback drill outcome and rollback duration
- Snapshot retention checks for active and paused runs
- Recorded operator rationale for any override or waiver
