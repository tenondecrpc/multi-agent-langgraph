## Context

This phase captures the platform substrate that will host the runtime SDD flow defined in phase 1. `docs/PLAN.md` already describes a self-hosted Kubernetes architecture, public APIs, queueing model, and gVisor sandbox plane, but those concerns need to be separated into stable capability specs before implementation begins.

## Goals / Non-Goals

**Goals:**
- Define the baseline self-hosted topology for connected and air-gapped deployments.
- Define the public API contract surface and versioning rules that later backend and frontend work must follow.
- Define the worker and queue operating model, including fair dispatch, shutdown, retry capture, and scaling assumptions.
- Define the sandbox execution plane as a hardened per-tenant Kubernetes job model.

**Non-Goals:**
- Authentication, RBAC, webhook signature validation, and credential encryption details.
- LLM provider routing, budgets, metering, or billing behavior.
- Admin graph configuration, shadow mode activation, or frontend control-room behavior.
- Observability, release engineering, or disaster recovery drill definitions.

## Decisions

- The product remains self-hosted only and single-customer at the infrastructure boundary, with both connected and air-gapped profiles treated as first-class from the design stage.
- The repository structure is planned up front as `backend/`, `frontend/`, `helm/`, and `docs/` so later phases can target concrete locations without inventing parallel layouts.
- Public APIs are versioned under `/api/v1`, while webhook intake and health endpoints remain explicit surfaces with their own contracts and later security controls.
- Worker behavior is defined separately from the runtime graph contract so queue fairness, graceful draining, and DLQ handling can be validated independently.
- Sandbox execution uses hardened Kubernetes Jobs with gVisor, per-tenant namespaces, non-root execution, egress restrictions, and cleanup jobs as baseline requirements rather than optional hardening.
- The `local-minikube` profile is a functional integration environment, not proof of production HA or SLO acceptance.

## Risks / Trade-offs

- Platform scope is broad, but deferring these requirements would let implementation couple runtime behavior to ad hoc deployment assumptions.
- Queueing, sandboxing, and API design all have downstream security implications, so this phase intentionally leaves some details to later security and operations phases while still freezing the baseline contract.
- Treating air-gapped support as first-class increases upfront planning complexity, but it avoids late architectural exceptions that would violate repository guardrails.

## Implementation Slice

The first executable platform slice now extends the backend implementation under `backend/`.

- `backend/src/backend/app.py` now exposes versioned `/api/v1` route groups for webhook intake, runs, streams, auth callback, admin profile, and metering export surfaces.
- `backend/src/backend/platform/api.py` centralizes the route inventory and minimal FastAPI routers used to prove the phase-2 endpoint categories and OpenAPI publication contract.
- `backend/src/backend/platform/queue.py` implements the weighted-fair dispatcher, worker drain lease model, and in-memory DLQ capture helpers used by the phase-2 verification tests.
- `backend/src/backend/platform/sandbox.py` implements the sandbox template builder and worker-pool profiles for primary and shadow execution contracts.
- `backend/tests/test_platform_contracts.py` verifies route inventory coverage, weighted-fair dispatch behavior, drain and DLQ semantics, and sandbox isolation defaults.

## Platform Baseline Coverage

This phase freezes the platform substrate required by the runtime flow from phase 1 without redefining phase 1 behavior.

| Platform concern | Contract outcome in this phase | Extension point in later phases |
|---|---|---|
| Deployment profiles | Connected and `air_gapped` remain first-class from the initial topology definition. | Phase 4 constrains provider routing in `air_gapped`; phase 7 validates HA and DR. |
| Repository structure | `backend/`, `frontend/`, `helm/`, and `docs/` become the required implementation roots. | Later phases add content under these roots but do not invent parallel top-level layouts. |
| Workload inventory | Frontend, API, primary workers, shadow workers, PostgreSQL, Redis, observability, and tenant sandbox jobs are baseline production workloads. | Phase 5 formalizes shadow behavior, phase 6 consumes API and stream surfaces, phase 7 adds reliability requirements. |
| Local development profile | `local-minikube` provides functional integration coverage only. | It never substitutes for production-grade security, HA, SLO, or DR validation. |
| Tier 1 alignment | Self-hosted deployment, Kubernetes-native execution, HPA planning, gVisor, tenant isolation, rate-aware queueing, and dead-letter support remain mandatory. | Later phases may strengthen enforcement, not weaken the baseline. |

This phase explicitly inherits phase 1 constraints:

- Worker and sandbox implementation must preserve checkpoint boundaries and the protected success path.
- Platform contracts may not bypass the planner-owned artifact chain or repo-write gate.
- Shadow workers are planned as a platform concern, but shadow-mode behavior remains defined in phase 5.

## API And Worker Contracts

### Future FastAPI Surface

The future backend should group public routes under explicit domains while publishing a single public OpenAPI contract rooted at `/api/v1`.

| Route group | Purpose | Notes |
|---|---|---|
| `/api/v1/webhooks` | Jira intake and related external webhook surfaces | Auth, HMAC, freshness, and rate limits are added by phase 3 without changing the route family. |
| `/api/v1/runs` | Run status, summaries, and detail lookup | Must align with the phase 1 run identity and artifact state model. |
| `/api/v1/streams` | Server-sent events for operator updates | Supports frontend monitoring and break-glass visibility later in phase 6. |
| `/api/v1/auth` | OIDC callback and session bootstrap surfaces | Session and authorization semantics are defined in phase 3. |
| `/api/v1/admin` | Graph, config, retry, DLQ, and policy administration | Feature-specific admin subroutes are added in phases 5 and 6. |
| `/api/v1/metering` | Metering export and billing-oriented read surfaces | Rollup and billing contracts are added in phase 4. |
| `/healthz` and `/readyz` | Health probes, not customer business APIs | These remain outside `/api/v1` and are treated as operational endpoints. |

OpenAPI publication rules:

- Every public `/api/v1` route must appear in the published OpenAPI document.
- Contract diffs must be reviewable before merge, with backward-incompatible changes requiring a new version or a documented deprecation path.
- Route additions may extend an existing group, but hidden production endpoints are not allowed outside the published inventory.

### Backward-Compatibility Contract

The future API policy should distinguish between additive and breaking changes.

| Change type | Compatibility expectation |
|---|---|
| New endpoint or optional response field | Allowed in `/api/v1` after OpenAPI diff review |
| Required request field, removed field, semantic response change | Requires a deprecation window or a new API version |
| Internal refactor without public schema impact | No version change required, but endpoint inventory must remain intact |

### Future Worker And Queue Interfaces

The platform should keep queue operations explicit instead of hiding them behind runtime graph code.

```python
class QueueDispatchPolicy(Protocol):
    async def select_next_job(self, now: datetime) -> "QueuedJob": ...


class WorkerLifecycleController(Protocol):
    async def begin_drain(self, worker_id: str, reason: str) -> "DrainLease": ...
    async def checkpoint_safe_to_exit(self, worker_id: str, job_id: str) -> bool: ...


class DeadLetterRecorder(Protocol):
    async def record(self, failed_job: "FailedJobRecord") -> "DeadLetterRef": ...
```

Worker contract expectations:

- ARQ settings must declare queue name, concurrency, retry budget, starvation threshold, and graceful-shutdown timeout as explicit configuration.
- Weighted-fair dispatch must combine per-tenant concurrency caps with starvation promotion so a large tenant cannot monopolize the worker fleet.
- Worker shutdown must stop new job acceptance before it attempts to terminate in-flight work.
- Draining is complete only after the job reaches a checkpoint-safe boundary or is explicitly captured for later resume.

### DLQ And Retry Capture Contract

Irrecoverable jobs must remain inspectable and retryable.

| Field | Purpose |
|---|---|
| `job_id`, `queue_name`, `tenant_id`, `team_id`, `run_id`, `thread_id` | Identify the failed execution scope |
| `failed_node`, `failure_reason`, `retry_count`, `terminal_at` | Explain why the job left the active queue |
| `checkpoint_ref`, `config_snapshot_id`, `artifact_refs` | Preserve deterministic resume context |
| `operator_summary`, `suggested_action`, `last_error_excerpt` | Support operator recovery workflows |

Retry rules:

- The DLQ record must preserve the last checkpoint reference instead of requiring operators to reconstruct state from logs.
- Re-dispatch from DLQ creates a new queue attempt but reuses the same phase 1 execution identity unless the operator explicitly forks a new run.
- Phase 3 later adds authorization rules around who may inspect or replay DLQ items.

## Sandbox And Namespace Contracts

### Future Kubernetes Job Template

Sandbox execution should be represented by a stable job template contract:

| Template field | Baseline rule |
|---|---|
| Namespace | Tenant-scoped namespace or equivalent isolated boundary |
| Runtime class | gVisor `runsc` or an equivalent hardened runtime |
| Security context | Non-root user, read-only root filesystem where possible, dropped Linux capabilities |
| Image | Minimal signed image with a bounded toolset for the assigned role |
| Volumes | Ephemeral writable volumes scoped to the sandbox job, not shared across tenants |
| Identity | Service account bound to least-privilege policies for the job type |
| TTL and cleanup labels | Required so cleanup jobs can distinguish active from orphaned resources |

### Network, Egress, And Quota Boundaries

The future sandbox plane must declare isolation as policy, not convention.

| Control | Baseline requirement |
|---|---|
| Egress policy | Default deny, then allow only approved destinations for the active ticket flow |
| Resource quota | Per-tenant CPU, memory, pod, and volume caps for sandbox namespaces |
| Cleanup | Scheduled cleanup jobs remove orphaned Jobs, Pods, PVCs, and scratch volumes |
| Ownership labels | Every sandbox resource carries tenant, run, and expiry labels for traceability |

Cleanup rules:

- Cleanup must never remove a resource still referenced by a live run or active lease.
- Quotas must be sufficient for bounded parallelism but must not allow unbounded tenant amplification through failed cleanup.

### Primary Worker And Shadow Worker Relationship

This phase plans the two worker pools without implementing phase 5 shadow behavior.

| Worker pool | Purpose in this phase | Guardrail |
|---|---|---|
| Primary worker pool | Executes the real ticket pipeline and can schedule writable sandbox jobs when phase 1 readiness conditions are met. | Must respect the repo-write gate and all runtime guards. |
| Shadow worker pool | Reserved for future read-only validation and config-candidate comparisons. | May not be treated as a production write path in this phase. |

Platform implications:

- The pools should be separately addressable for capacity planning, service identity, and queue routing.
- Shared infrastructure such as PostgreSQL and Redis may be reused, but queue names, service accounts, and metrics labels must keep the pools distinguishable.
- Phase 5 defines shadow activation logic, evidence comparison, and rollback interactions on top of this baseline separation.

## Verification Fixtures

| Task | Fixture definition | Expected proof |
|---|---|---|
| 4.1 API dry-run validation | Compare the declared endpoint inventory and generated OpenAPI schema against the prior published contract. | Missing route groups, unversioned public endpoints, or breaking schema changes fail validation. |
| 4.2 Worker drain and DLQ capture | Simulate SIGTERM during an active job and a terminal retry exhaustion path. | The worker stops taking new jobs, preserves checkpoint-safe progress, and records exhausted jobs to the DLQ with replay metadata. |
| 4.3 Sandbox boundary validation | Launch representative sandbox jobs under multiple tenants with quota and cleanup controls enabled. | Jobs remain tenant-scoped, run non-root with the hardened runtime, respect quota ceilings, and are removable by cleanup after expiry. |

These fixtures should seed later implementation suites:

- Phase 3 adds auth, webhook, and repo-safety variants to the same API and worker paths.
- Phase 5 adds shadow queue and activation validation on top of the primary-versus-shadow pool split.
- Phase 7 promotes the drain, quota, and topology fixtures into operational acceptance tests for release.
