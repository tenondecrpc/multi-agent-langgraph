# Runbook: Persistence Circuit Breaker Open

## Alert: ProviderCircuitBreakerOpen

### Summary
The LLM provider circuit breaker has opened due to consecutive failures.

### Impact
- All LLM requests to the affected provider are blocked.
- The system will attempt provider failover if configured.
- If all providers are unavailable, ticket processing halts.

### Diagnosis

1. Check `provider_health_events` for failure counts and last probe time.
2. Inspect backend logs for specific provider errors (timeout, 429, 5xx).
3. Verify provider endpoint reachability from the cluster.

### Mitigation

1. If transient: wait for the half-open probe to succeed (automatic recovery).
2. If rate-limited: back off and review per-ticket/per-team token budgets.
3. If provider is down: trigger manual failover or update the endpoint URL.

### Verification

- Confirm `provider_health_store` shows `state: closed` for the provider.
- Run a test simulation via `/api/v1/runtime/simulate`.

### Escalation
If no provider recovers within the SLO window, escalate to `ops://llm-routing`.
