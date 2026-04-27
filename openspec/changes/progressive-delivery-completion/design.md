## Architecture Reuse

This change extends, not replaces, existing systems:

- Argo Rollouts: the existing `helm/templates/rollout.yaml`, `analysis-template.yaml`, `frontend-rollout.yaml`, and `worker-rollout.yaml` are completed, not rewritten.
- OpenFeature: provider plug points already exist under `backend/src/backend/operations/feature_flags.py` and `feature_flag_service.py`; this change defines the operational contract on top of them.
- PostgreSQL config: kill-switch state lives in the same versioned config tables that govern the runtime graph; shadow-mode validation is reused, not duplicated.
- Prometheus + Alertmanager: SLO burn-rate alerts already exist; the rollout analysis template consumes them rather than defining a parallel signal source.

## Promotion Gates

A canary stage may advance only if all of the following hold:

1. The image digest has a valid cosign signature and SLSA Level 3 provenance attestation (admission policy already enforces this).
2. The SLO burn-rate signals (latency, error, saturation) stay under the abort threshold for the analysis window.
3. No active SEV1 or SEV2 incident is open against the affected service.
4. No high-risk kill switch is in `denied` state for the capability being promoted.

If any gate fails, the rollout aborts and traffic returns to the stable revision automatically.

## Kill-Switch Capabilities In Scope

| Capability                              | Default | Failure Mode When Service Unreachable |
|-----------------------------------------|---------|---------------------------------------|
| `provider_routing_override`             | off     | last-known-good                       |
| `sandbox_enforcement`                   | on      | last-known-good (never fail-open)     |
| `internal_rag_enabled`                  | off     | last-known-good                       |
| `webhook_acceptance`                    | on      | last-known-good                       |
| `pr_creation`                           | on      | last-known-good                       |
| `admission_enforce_mode`                | off     | last-known-good (never relax)         |

Adding new high-risk flags requires an OpenSpec change that updates this table.

## Persistence And Audit

- Flag state is stored in `feature_flag_states` and `feature_flag_state_versions` tables in PostgreSQL, owned by the same control-plane store as graph configuration. No new datastore is introduced.
- Every flip writes an audit row with actor, before, after, justification, and shadow-mode result.
- Shadow mode evaluates a candidate flag state for a configurable window before activation, mirroring the runtime graph shadow-mode contract.

## Air-Gapped Profile

- Helm `values-air-gapped.yaml` must include the flag-service deployment locally; no vendor-hosted SaaS provider is permitted.
- Pods cache the last-known-good flag map on disk under a tmpfs path; cache TTL is bounded to prevent indefinite drift.
- A boot probe verifies the flag service is reachable; if not, the pod records a degraded readiness reason but stays alive on cached state.

## Observability

- Metrics: `devsquad_rollout_phase`, `devsquad_rollout_aborts_total`, `devsquad_kill_switch_state{capability=...}`, `devsquad_kill_switch_propagation_seconds`, `devsquad_flag_service_unreachable_total`.
- Alerts: rollout aborted, kill switch flipped to deny on a Tier 1 capability, flag service unreachable beyond cache TTL.
- Dashboards: rollout-history, kill-switch-state, flag-propagation-latency.

## Failure Modes And Rollback

- Stuck rollout: operator runs `kubectl argo rollouts abort <name>`, escalation sink `ops://release` records the rationale.
- Stuck kill switch: dual super-admin approval to force-clear, audit row required.
- Flag-service outage: existing `docs/runbooks/flag-service-outage.md` is updated to reflect last-known-good guarantees and air-gapped degradation.

## Protected Workflow Invariants

- This change does not introduce any new path that can reach PR creation; it governs how new versions of existing services are rolled out.
- Human approval remains break-glass only on stuck-flag and stuck-rollout exception paths.
