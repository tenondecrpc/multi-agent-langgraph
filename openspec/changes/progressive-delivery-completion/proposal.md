## Why

`STATUS.md` flags `progressive-delivery-and-feature-flag-kill-switches` as an open Tier 1 production blocker. Helm packaging is described as "baseline, not production-complete" and the existing `rollout.yaml` template is not yet wired into a validated Argo Rollouts pipeline. Kyverno admission policies still ship in Audit mode because there is no tested progressive-delivery path that can roll forward and roll back signed images safely.

The constitution requires automated rollback, OpenFeature-driven kill switches for high-risk runtime capabilities, and signed-and-attested images promoted only through progressive delivery. Today none of those flows are validated end to end.

## What Changes

- Define the Argo Rollouts canary plan for backend, worker, and frontend deployments, including analysis templates, success criteria, and abort thresholds.
- Define the OpenFeature kill-switch contract for high-risk runtime capabilities (provider routing override, sandbox enforcement, internal RAG, webhook acceptance, PR creation, admission enforce mode flip).
- Define the kill-switch drill cadence and operator UI surface that proves a flag flip propagates to running pods within an SLO.
- Define the rollback-on-SLO-burn behavior tied to existing burn-rate alerts.
- Define how flag state is persisted in PostgreSQL config with shadow mode validation, audit, and rollback - the flag store is not a parallel system.
- Define the air-gapped-safe degradation path for the flag service (local cache, last-known-good, denial of new flag activations rather than fail-open).
- Document rollout promotion gates: only signed and SLSA-attested images can advance through canary stages.

## Capabilities

### Modified Capabilities

- `release-engineering-and-feature-flags`: complete the canary, analysis, and rollback pipeline; require flag state to live in versioned PostgreSQL config with shadow mode.
- `progressive-delivery-and-kill-switches`: add operator-facing kill-switch CRUD, drill schedule, propagation SLO, and audit trail.

## Tier Classification

This change addresses a Tier 1 non-negotiable. It does not weaken any Tier 1 rule; it completes one already promised by the constitution.

## Non-Goals

- Multi-cluster federation of Argo Rollouts.
- Replacing OpenFeature with a custom evaluation engine.
- Region-aware traffic shifting beyond a single customer-owned cluster.
- Adding new high-risk capabilities; this change only governs the ones already in scope.

## Operational Impact

- New Argo Rollouts CRDs in customer clusters; dependency must be present in both connected and air-gapped Helm charts.
- Flag service outage runbook (`docs/runbooks/flag-service-outage.md`) must reflect the air-gapped degradation contract.
- Admission can flip from Audit to Enforce only after a validated canary completes and rollback is proven.

## Risk

- A misconfigured analysis template can stall releases.
- A poorly scoped kill switch can disable a critical capability cluster-wide.
- Air-gapped clusters with stale cached flag state could behave differently from the connected profile.

## Rollback / Degradation

- Each canary stage MUST have an automated abort that returns 100% traffic to the stable revision.
- Each kill switch MUST have a documented "stuck flag" recovery procedure.
- Flag service outage MUST default to last-known-good; new high-risk capability activations MUST be denied during outage.
