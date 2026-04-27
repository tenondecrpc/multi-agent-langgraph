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

| Gate | Input | Abort threshold | Evidence |
|------|-------|-----------------|----------|
| Signature and provenance | Cosign signature, SBOM reference, SLSA Level 3 attestation | Missing, expired, unverifiable, or mismatched image digest | Admission decision and attestation bundle |
| SLO burn rate | Existing Prometheus latency, error, saturation, circuit-breaker, DLQ, and pool metrics | Any protected indicator exceeds the per-service abort threshold for the analysis window | Argo Rollouts analysis run |
| Incident state | Active incident feed for the affected service | Any active SEV1 or SEV2 incident | Incident id and release hold reason |
| Kill-switch state | OpenFeature evaluation plus PostgreSQL mirror | Capability required for the rollout is `denied`, `stale`, or unknown past TTL | Flag state version and audit row |
| Policy mode | Admission and runtime policy state | Enforce-mode promotion without validated audit-mode canary | Policy report and rollout id |

## Canary Stages

Backend and worker services use Argo Rollouts canary stages. The frontend keeps blue/green semantics because user-facing static assets need a clean promote or abort boundary.

| Component | Strategy | Stages | Pause window | Analysis |
|-----------|----------|--------|--------------|----------|
| Backend API | Canary | 5%, 25%, 50%, 100% | 10 minutes at 5%, 10 minutes at 25%, 15 minutes at 50% | Error rate, p95 latency, saturation, circuit-breaker opens, DLQ growth |
| Worker | Canary | 5%, 25%, 50%, 100% by queue shard or worker replica cohort | 15 minutes at 5%, 15 minutes at 25%, 20 minutes at 50% | Job failure rate, retry growth, checkpoint lag, DLQ growth, pool saturation |
| Frontend | Blue/green | Preview, smoke, promote active, retire previous | Manual promote must occur within 30 minutes after green smoke | Smoke status, API compatibility probe, asset integrity, client error rate |

The analysis template consumes existing burn-rate recording rules instead of introducing a new metrics pipeline. Suggested initial abort thresholds are:

- API error burn rate greater than 2x over 10 minutes or greater than 1x over 30 minutes.
- API p95 latency burn rate greater than 2x over 10 minutes.
- Saturation above 85% for the analysis window.
- Any provider circuit breaker open ratio above 5% for the candidate cohort.
- DLQ growth above 10 new entries per 10 minutes for the affected queue.
- Worker checkpoint lag above 2 minutes for the candidate cohort.

Rollout aborts are automatic when an analysis check fails. Stuck rollout aborts are break-glass only, require `ops://release`, and write actor, rationale, timestamp, rollout name, stable revision, candidate revision, and analysis link.

## Kill-Switch Capabilities In Scope

| Capability | Flag key | Default | Failure mode when service unreachable | Rollback path |
|------------|----------|---------|---------------------------------------|---------------|
| Provider routing override | `ops.provider_routing_override` | off | last-known-good, then deny new override activation | Clear override and fall back to configured provider policy |
| LLM provider enablement | `llm_provider_anthropic`, `llm_provider_openai` | on | last-known-good, then deny provider enable changes | Disable affected provider and route through configured fallback |
| Sandbox enforcement | `sandbox_runtime_gvisor` | on | last-known-good, never fail-open | Keep sandbox enforced and pause affected runs |
| Internal RAG | `ops.internal_rag_enabled` | off | last-known-good, then disabled | Disable retrieval and continue local-first context resolution |
| Webhook acceptance | `ops.webhook_acceptance` | on | last-known-good, then reject new webhooks with retryable status | Restore previous accepted state and rely on Jira retry |
| PR creation | `pr_creation` | on | last-known-good, then deny new PR creation | Pause at pre-PR escalation before repo write completion |
| Graph activation | `graph_activation` | on | last-known-good, then deny new graph activation | Continue last active graph version |
| Ticket processing | `ticket_processing` | on | last-known-good, then stop dequeueing new tickets | Drain in-flight work to checkpoint boundary |
| Admission enforce mode | `ops.admission_enforce_mode` | off | last-known-good, never relax enforce to audit after activation | Return candidate policy to audit and keep stable enforcement state |

Adding new high-risk flags requires an OpenSpec change that updates this table.

Kill-switch propagation SLO is 60 seconds from persisted flag-state version to observation by 99% of running backend, worker, and frontend pods, and 120 seconds for 100% of pods. The system records per-pod observation timestamps and emits `devsquad_kill_switch_propagation_seconds`.

Operator UI requirements:

- Show read-only flag key, capability, default, current state, source version, stale status, last actor, last justification, and observed pod count.
- Allow tenant-scoped read for tenant admins and global read for super admins.
- Require dual-control super-admin approval for fail-closed flags and for stuck-flag force-clear.
- Show shadow-mode result before activation and block activation when shadow mode reports policy regression.
- Never expose secret values, SDK keys, or provider credentials.

## Persistence And Audit

- Flag state is stored in `feature_flag_states` and `feature_flag_state_versions` tables in PostgreSQL, owned by the same control-plane store as graph configuration. No new datastore is introduced.
- Every flip writes an audit row with actor, before, after, justification, and shadow-mode result.
- Shadow mode evaluates a candidate flag state for a configurable window before activation, mirroring the runtime graph shadow-mode contract.
- `feature_flag_states` stores `tenant_id`, `team_id`, `flag_key`, `capability`, `current_state`, `default_state`, `fail_closed`, `version`, `owner`, `created_at`, `updated_at`, `last_actor`, `last_justification`, and `expires_at`.
- `feature_flag_state_versions` stores `state_id`, `version`, `before_state`, `after_state`, `actor`, `approver_actor`, `justification`, `shadow_result`, `shadow_window_seconds`, `source`, `created_at`, and `rollback_of_version`.
- High-risk flags require a 10 minute shadow-mode validation window before activation unless the action is a break-glass deny action that makes the system stricter. Shadow mode must validate repo-write gates, sandbox enforcement, provider routing, and policy-mode effects against synthetic traffic.

## Air-Gapped Profile

- Helm `values-air-gapped.yaml` must include the flag-service deployment locally; no vendor-hosted SaaS provider is permitted.
- Pods cache the last-known-good flag map on disk under a tmpfs path; cache TTL is bounded to prevent indefinite drift.
- A boot probe verifies the flag service is reachable; if not, the pod records a degraded readiness reason but stays alive on cached state.
- The local flag service is deployed from the chart, backed by PostgreSQL, and initialized from a signed ConfigMap or sealed bundle shipped with the release.
- Last-known-good cache path is `/var/run/devsquad/feature-flags/cache.json` on tmpfs. The default TTL is 10 minutes in connected mode and 30 minutes in `air_gapped` mode.
- Cache eviction occurs on version supersession, signature mismatch, tenant scope mismatch, or pod restart. Operators can reset the cache only by restarting pods or using a documented break-glass command that records an audit row.
- When the flag service is unreachable past TTL, pods deny new high-risk activations and never relax existing fail-closed defaults. Already-active stricter states remain effective until a valid newer state is observed.

## Observability

- Metrics: `devsquad_rollout_phase`, `devsquad_rollout_aborts_total`, `devsquad_kill_switch_state{capability=...}`, `devsquad_kill_switch_propagation_seconds`, `devsquad_flag_service_unreachable_total`.
- Alerts: rollout aborted, kill switch flipped to deny on a Tier 1 capability, flag service unreachable beyond cache TTL.
- Dashboards: rollout-history, kill-switch-state, flag-propagation-latency.
- Additional metrics: `devsquad_rollout_analysis_failures_total{service,reason}`, `devsquad_flag_shadow_validation_failures_total{capability}`, `devsquad_flag_cache_age_seconds{pod,profile}`, and `devsquad_rollout_manual_aborts_total{service}`.
- Quarterly kill-switch drill picks one governed capability, flips it in staging, observes propagation against the SLO, restores the prior state, and files evidence with flag version, pod observations, metrics, audit rows, and screenshots or API output.
- Quarterly rollout-abort drill deliberately fails one staging analysis check, verifies automated rollback to the stable revision, and files evidence with rollout id, abort reason, stable revision, candidate revision, analysis run, and Alertmanager event.

## Failure Modes And Rollback

- Stuck rollout: operator runs `kubectl argo rollouts abort <name>`, escalation sink `ops://release` records the rationale.
- Stuck kill switch: dual super-admin approval to force-clear, audit row required.
- Flag-service outage: existing `docs/runbooks/flag-service-outage.md` is updated to reflect last-known-good guarantees and air-gapped degradation.
- Failed signature or provenance gate: abort rollout before traffic increase and keep admission enforcement authoritative.
- Burn-rate regression: automatically return 100% traffic to stable revision within 2 minutes of analysis failure.
- Incident gate blocks release: keep candidate paused until incident is resolved or manually abort through `ops://release`.
- Cache stale beyond TTL: deny new high-risk activations, keep stricter existing fail-closed behavior, and alert operations.

## Protected Workflow Invariants

- This change does not introduce any new path that can reach PR creation; it governs how new versions of existing services are rolled out.
- Human approval remains break-glass only on stuck-flag and stuck-rollout exception paths.
- Signed-and-attested image policy remains enforced by admission control and is not bypassed by the rollout controller.
- All state uses PostgreSQL-backed control-plane storage plus local pod cache; no new production datastore is introduced.
