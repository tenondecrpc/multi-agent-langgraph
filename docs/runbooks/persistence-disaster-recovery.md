# Runbook: Persistence Disaster Recovery

## Alert: PersistenceMigrationDrift

### Summary
The applied database migration revision does not match the expected head revision.

### Impact
- Schema drift can cause application errors or data integrity issues.
- New features requiring the latest schema may fail.

### Diagnosis

1. Check `/healthz` for `migration.state` and `migration.current_revision`.
2. Run `alembic current` to see the actual revision.
3. Run `alembic history --verbose` to see expected revisions.

### Mitigation

1. If behind: run `alembic upgrade head` in a maintenance window.
2. If ahead (rollback scenario): run `alembic downgrade <target>`.
3. If manual drift is detected, restore from the last verified backup.

### Verification

- Confirm `/healthz` shows `migration.state: up_to_date`.
- Run smoke tests against the affected endpoints.

### Escalation
If migration cannot be reconciled, escalate to `ops://database` and invoke the disaster-recovery playbook.
