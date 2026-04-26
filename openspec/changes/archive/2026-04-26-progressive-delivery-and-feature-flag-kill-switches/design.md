# Design: Progressive Delivery And Feature-Flag Kill Switches

## Context

Phase 7 established the direction; this change wires the rollout controller, analysis, and OpenFeature integration end-to-end. Without automated rollback tied to SLOs, a bad deploy can run to 100% before operators react.

## Goals / Non-Goals

### Goals

- Canary rollouts for API and worker; blue/green for frontend.
- SLO-driven `AnalysisTemplate` that fails the rollout when burn rates exceed thresholds.
- Six mandatory kill switches and a disciplined lifecycle for new flags.

### Non-Goals

- No replacement for runtime config versioning (that lives in the existing control plane).
- No vendor-hosted flag service; Unleash self-hosted or LaunchDarkly customer-owned only.

## Decisions

### Decision: Canary steps and automated analysis

API and worker Rollouts use steps 5 -> 25 -> 50 -> 100 with pauses between. Each pause runs an `AnalysisTemplate` that evaluates: error rate, latency p95, circuit-breaker open events, DLQ growth, pool saturation. Any failing metric triggers rollback.

### Decision: Air-gapped flag service

For `air_gapped`, Unleash runs inside the cluster. Flag state is mirrored to a PostgreSQL `feature_flag_state` table for audit and for read-through access when the flag service is briefly unavailable (fail-safe with last-known state and TTL).

### Decision: Six mandatory kill switches

Flags: `llm_provider_anthropic`, `llm_provider_openai`, `pr_creation`, `graph_activation`, `sandbox_runtime_gvisor`, plus a global `ticket_processing`. Each is a boolean with per-tenant targeting and audit on toggle.

### Decision: Stale-flag discipline

Any flag older than 90 days without change or removal alerts the owning team. PR templates include a flag-cleanup checklist.

## Risks / Trade-offs

- Analysis tuning false positives. Mitigated by staging soak and tunable thresholds per service.
- Flag-service outage. Mitigated by PostgreSQL mirror and documented fail-safe semantics.

## Migration Plan

1. Introduce Argo Rollouts Helm dependency in staging only.
2. Migrate API Deployment to Rollout; add AnalysisTemplate; soak.
3. Migrate worker Deployment.
4. Migrate frontend to blue/green.
5. Introduce the six flags; wire kill-switch drill (toggle off in staging).
