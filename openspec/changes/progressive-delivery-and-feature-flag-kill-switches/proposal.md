## Why

The constitution mandates progressive delivery with automated rollback and feature-flag kill switches for high-risk runtime capabilities. PLAN.md specifies Argo Rollouts canary (5 -> 25 -> 50 -> 100) with Prometheus SLO analysis and automated rollback, blue/green for frontend, and six mandatory v1 OpenFeature flags (LLM providers, PR creation, graph activation, sandbox runtime). Phase 7 covers observability and release engineering direction but not this specific wiring.

## What Changes

- Adopt Argo Rollouts for API and worker Deployments with canary steps and Prometheus `AnalysisTemplate` driven by persistence and runtime SLOs.
- Blue/green rollout for the frontend via Argo Rollouts.
- OpenFeature-based kill switches for the six mandatory flags; flag state lives in Unleash or LaunchDarkly and is replicated to a PostgreSQL mirror for audit and air-gapped read.
- Flag lifecycle discipline: stale-flag alerts after 90 days, audit log writes on every toggle, per-tenant targeting rules.
- Tenant-scoped rollout safeguards: no canary step without persistence and runtime SLO metrics being healthy.

## Capabilities

### New Capabilities

- `progressive-delivery-and-kill-switches`: canary and blue/green rollout contract, SLO-driven automated rollback, feature-flag kill-switch set and lifecycle.

### Modified Capabilities

- `release-engineering-and-feature-flags`: adds the specific rollout steps, analysis templates, and flag catalog.
- `service-level-objectives-and-alerting`: SLO queries feed the rollout analysis templates.

## Impact

- Code: `helm/` Rollout resources, `AnalysisTemplate` YAML, flag-client wrapper module in `backend/src/backend/operations/`.
- Schema: `feature_flag_audit` and `feature_flag_state` mirror table (read-through from Unleash or LaunchDarkly).
- Deployment: Argo Rollouts controller Helm dependency; connected and `air_gapped` profile values.
- Observability: rollout-state, analysis-failure, and flag-toggle metrics and runbooks.
- Tests: rollout chaos test that injects SLO breach and verifies automated rollback.
- Constitution alignment: Tier 1 preserved.
