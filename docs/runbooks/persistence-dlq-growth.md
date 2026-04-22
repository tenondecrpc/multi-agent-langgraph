# Runbook: DLQ Growth

## Trigger

- `devsquad_dlq_depth` grows faster than normal retry recovery.

## Checks

- Query `dead_letter_records` ordered by `created_at`.
- Verify whether `checkpoint_ref` is present for restartable runs.
- Inspect queue starvation and tenant concurrency counters.

## Response

- Pause new assignments for the affected tenant if repeated checkpoint recovery fails.
- Retry only from preserved checkpoint refs.
- Escalate to `security_review` if failure reasons suggest policy or secret handling issues.
