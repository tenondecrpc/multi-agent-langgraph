# Runbook: All Providers Down

## Trigger

All configured LLM providers are unavailable, provider routing has no healthy fallback, or the Redis-shared circuit breaker has opened every eligible provider for a tenant or team.

## Impact

Planner, coder, tester, reviewer, and PR creation work that requires model calls cannot progress. Existing checkpoints must remain durable, and no repo-writing node may bypass the SDD readiness gate or review chain.

## Triage

1. Confirm the deployment profile: `connected` or `air_gapped`.
2. Check provider health metrics and recent `provider_health_events` for each configured provider.
3. Verify Redis connectivity, because circuit-breaker state is shared through Redis in the production adapter path.
4. Confirm budget reservations are not falsely denying calls due to a ledger or clock issue.
5. Inspect the model catalog for tenant and team allowlist drift.

## Response

1. Keep repo-writing nodes paused at checkpoint boundaries.
2. In connected deployments, validate upstream provider availability and customer-owned provider credentials.
3. In `air_gapped`, validate the self-hosted model endpoint and keep external vendor egress blocked.
4. Move one provider to half-open only after a successful probe.
5. Resume ticket execution from checkpoints after at least one approved provider is healthy.

## Escalation

Escalate as SEV1 when no tenant can process tickets, when data-integrity risk exists, or when provider failover violates the configured allowlist. Escalate as SEV2 for isolated provider exhaustion with a working fallback.

## Evidence

- Affected tenants and teams
- Provider health state per provider
- Circuit-breaker transition timestamps
- Checkpoint resume confirmation
- Operator who reopened provider traffic
