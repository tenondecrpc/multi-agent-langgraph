# Runbook: Persistence DLQ Growth

## Alert: PersistenceDlqGrowth

### Summary
The dead-letter queue for worker jobs is growing faster than it is being drained.

### Impact
- Tickets may stall indefinitely.
- Worker capacity is effectively reduced.
- DLQ saturation can trigger circuit-breaker open state.

### Diagnosis

1. Check the `worker_controller` metrics for `dlq_growth_rate`.
2. Inspect DLQ entries in PostgreSQL (`dead_letter_queue` table).
3. Check worker logs for repeated failure patterns.

### Mitigation

1. If workers are down, restart the worker deployment.
2. If a specific job type is failing, disable it via the feature-flag kill switch.
3. For poison messages, manually purge or requeue after fixing the root cause.

### Verification

- Confirm DLQ growth rate returns to zero or negative.
- Check that queued jobs are being processed.

### Escalation
If DLQ continues growing after worker restart, escalate to `ops://runtime-pipeline`.
