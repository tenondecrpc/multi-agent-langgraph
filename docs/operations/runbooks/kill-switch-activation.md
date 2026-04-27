# Runbook: Kill-Switch Activation

## Trigger

Operator needs to disable a high-risk subsystem without redeploying.

## Mandatory Kill Switches

| Flag Key | Owner | Description |
|---|---|---|
| `llm_provider_anthropic` | llm-governance | Kill switch for Anthropic provider routing |
| `llm_provider_openai` | llm_provider_openai | Kill switch for OpenAI provider routing |
| `pr_creation` | runtime-pipeline | Kill switch for PR creation node |
| `graph_activation` | runtime-pipeline | Kill switch for graph execution activation |
| `sandbox_runtime_gvisor` | sandbox-execution | Kill switch for gVisor sandbox runtime |
| `ticket_processing` | runtime-pipeline | Global kill switch for ticket processing |

## Steps

### 1. Identify the Target Kill Switch

Determine which subsystem needs to be disabled. Use the table above to find the correct flag key.

### 2. Activate the Kill Switch

Via Unleash UI:

1. Navigate to the Unleash admin console
2. Find the flag by key name
3. Toggle to `OFF`
4. Add a reason in the audit comment field

Via API:

```bash
curl -X POST http://unleash-web:4242/api/admin/features/<flag-key>/off \
  -H "Authorization: <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "<reason for activation>"}'
```

### 3. Verify Kill Switch Activation

```bash
# Check flag state in PostgreSQL mirror
psql -c "SELECT flag_key, enabled, updated_at FROM feature_flag_state WHERE flag_key = '<flag-key>';"

# Check audit log
psql -c "SELECT * FROM feature_flag_audit WHERE flag_key = '<flag-key>' ORDER BY changed_at DESC LIMIT 5;"
```

### 4. Confirm Subsystem Behavior

- For provider kill switches: verify routing falls back to remaining providers
- For PR creation: verify tickets pause at the PR creation guard
- For graph activation: verify new tickets are rejected at intake
- For sandbox: verify code execution falls back to safe mode
- For ticket processing: verify webhook intake returns 503

### 5. Monitor Impact

- Check Prometheus dashboards for the affected subsystem
- Monitor DLQ depth for backed-up work
- Check SLO burn rate for the affected service

### 6. Deactivate the Kill Switch

When the issue is resolved, re-enable the flag:

```bash
curl -X POST http://unleash-web:4242/api/admin/features/<flag-key>/on \
  -H "Authorization: <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "<reason for deactivation>"}'
```

## Fail-Closed Behavior

If the flag service (Unleash/LaunchDarkly) is unavailable, kill switches default to `OFF` (disabled state). The PostgreSQL mirror provides last-known state with a TTL of 300 seconds.

## Escalation

If kill switch activation does not take effect within 60 seconds:

1. Check flag service connectivity
2. Check PostgreSQL mirror sync status
3. Escalate to the platform team

## Related Runbooks

- `canary-rollback.md`
- `flag-service-outage.md`
