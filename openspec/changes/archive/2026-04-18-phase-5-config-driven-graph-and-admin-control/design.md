## Context

This phase defines the control plane that governs runtime behavior without requiring source-code edits for normal operations. The repository constitution already requires PostgreSQL-backed config, versioning, rollback, and shadow validation, so the graph and agent configuration surfaces need explicit OpenSpec contracts before backend and frontend implementation begin.

## Goals / Non-Goals

**Goals:**
- Define a config-driven graph runtime that still preserves all protected workflow invariants.
- Define a read-only shadow-mode activation path that produces evidence before a new config becomes active.
- Define agent configuration as a validated, least-privilege surface rather than a free-form prompt and tool editor.
- Define versioning, audit, rollback, and snapshot pinning for graph and agent config changes.

**Non-Goals:**
- Kubernetes deployment internals or sandbox hardening details.
- Tenant auth, webhook trust, or provider budgeting details.
- Frontend interaction design for graph editing or dashboard visuals.
- Release rollout, SLO policy, or chaos testing details.

## Decisions

- Runtime topology remains config-driven, but activatable graphs are validated against protected v1 invariants instead of being treated as arbitrary DAGs.
- Graph validation is stronger than simple compile success. A graph that compiles but bypasses required guards is still invalid for activation.
- Shadow mode uses separate credentials, queueing, service identity, and network policy to provide defense in depth rather than relying on a single application-level read-only flag.
- Agent config is modeled as a role-bound operational contract. Admins may tune within role limits, but they may not grant arbitrary tools or bypass least-privilege boundaries.
- Config versions are stored in PostgreSQL with audit trail and rollback. New versions apply only to new runs, while active or paused runs keep their pinned snapshot until completion.
- Dry-run or test-agent surfaces are part of the control-plane contract, but they remain subject to the same model, tool, and validation rules as production config.

## Risks / Trade-offs

- A flexible graph editor without invariant validation would be dangerous, so this phase intentionally prioritizes safety over maximum graph freedom.
- Shadow mode is operationally expensive because it duplicates some runtime infrastructure, but it provides concrete evidence before risky activations.
- Versioned config and snapshot retention add state-management complexity, but they are necessary to keep retries and resumes deterministic across config changes.

## Control-Plane Coverage

This phase defines the runtime control plane without weakening the archived runtime, platform, security, or LLM contracts.

| Control-plane concern | Contract outcome in this phase | Protected dependency |
|---|---|---|
| Graph configuration | Runtime topology becomes config-driven through validated graph documents and handler references. | Must preserve phase 1 readiness, test, review, pre-PR sync, and escalation rules. |
| Agent configuration | Role-scoped model, prompt, tool, and retry settings become validated config instead of source-code constants. | Must preserve phase 3 role boundaries and phase 4 model and budget constraints. |
| Shadow mode | Candidate configs are tested through isolated read-only execution before activation. | Reuses phase 2 worker separation and phase 3 least-privilege controls. |
| Versioning and activation | Graph and agent configs are versioned in PostgreSQL with audit trail and snapshot pinning. | Must keep the phase 1 pinned run snapshot model intact. |
| Rollback | Operators can revert to prior versions for new runs without breaking in-flight or paused work. | Must not invalidate referenced snapshots for non-terminal runs. |

Constitution alignment:

- PostgreSQL-backed config storage remains mandatory.
- Shadow validation remains mandatory before ordinary activation.
- Compile success is insufficient without invariant validation.
- New configs affect only new runs; existing runs stay pinned to their accepted snapshot.

## Graph And Agent Configuration Interfaces

### Future Graph Config Schema And Handler Registry

The graph control plane should use a typed config contract instead of arbitrary free-form DAG editing.

```python
class GraphConfigVersion(BaseModel):
    config_version_id: str
    profile_id: str
    graph_nodes: list["GraphNodeConfig"]
    graph_edges: list["GraphEdgeConfig"]
    route_handlers: list["RouteHandlerRef"]
    invariant_profile: Literal["ticket_to_pr_v1"]
    created_by: str
    created_at: datetime


class RouteHandlerRef(BaseModel):
    handler_name: str
    handler_version: str
    handler_kind: Literal["system", "tenant_configurable"]
```

Schema expectations:

- Node configs must identify whether they are protected system handlers or tenant-configurable extensions.
- Edge configs must declare success, retry, escalation, and terminal transitions explicitly.
- Handler references resolve through a registry so configs refer to known code paths rather than arbitrary executable content.
- The `ticket_to_pr_v1` profile is protected: required system handlers cannot be removed or replaced by untrusted equivalents.

### Route Validation And Invariant Checks

The graph compiler should separate technical compilation from safety validation.

```python
class GraphValidationResult(BaseModel):
    compiles: bool
    invariant_errors: list[str]
    missing_escalation_sinks: list[str]
    protected_path_violations: list[str]
```

Required invariant checks:

- Every PR-reaching path traverses readiness gate, coder, tester, reviewer, and pre-PR sync.
- No route enables repo-writing before `spec_ready_for_implementation=true` and a task list exists.
- Manual approval exists only on registered break-glass exception paths.
- Every terminal failure route maps to a registered escalation sink.
- Required system handlers for `ticket_to_pr_v1` remain present and connected.

### Future Agent Config Schema And Dry-Run Interface

```python
class AgentConfigVersion(BaseModel):
    agent_role: Literal["planner", "coder", "tester", "reviewer", "pr_creator"]
    model_id: str
    fallback_model_id: str | None = None
    system_prompt_ref: str
    allowed_tools: list[str]
    retry_limits: dict[str, int]
    token_policy_ref: str
```

Agent config rules:

- Role names are fixed to the supported runtime roles.
- `allowed_tools` must validate against the phase 3 role boundary and the phase 4 model catalog and budget policy.
- Retry settings may tune bounded behavior but may not remove mandatory retry ceilings or disable escalation mapping.
- Dry-run or test-agent requests must execute against a validated candidate config and may not grant broader privileges than production.

## Activation Workflow

The future activation path should be explicit and auditable.

| Activation stage | Required behavior |
|---|---|
| Draft | New graph or agent config version is created in PostgreSQL with actor and rationale metadata |
| Compile | Graph topology and handler references compile successfully against the current registry |
| Validate | Invariant checks, role policy checks, model catalog validation, and shadow prerequisites all pass |
| Shadow evaluate | Candidate config runs in isolated read-only mode and produces comparison evidence |
| Approve activation | Activation decision records actor, evidence summary, and any override rationale |
| Snapshot and rollout | A new active snapshot is created for future runs and worker rollout picks up the new version |

Activation rules:

- Activation is blocked if compile or validation passes but shadow evidence fails configured thresholds.
- Overrides are auditable exception paths, not silent bypasses.
- Snapshot creation must pin both graph and agent config versions together so future runs resolve a coherent control-plane state.

## Shadow And Rollback Interfaces

### Shadow Queue, Credentials, And Worker Isolation

Shadow mode should reuse the runtime shape while preventing side effects through multiple layers.

| Isolation layer | Contract |
|---|---|
| Queueing | Shadow runs use separate queue names and consumer groups from primary execution |
| Workers | Shadow workers have distinct deployment identity, metrics labels, and scaling policy |
| Credentials | Read-only credentials prevent repository, Jira, and other write operations |
| Network policy | Shadow workers may reach only the read surfaces required for comparison |
| Application flags | Candidate runs are marked shadow at runtime so write handlers can refuse execution |

Shadow rules:

- No single control may be trusted as the only barrier against write side effects.
- Shadow runs use the same config snapshot semantics as primary runs, but the snapshot is marked candidate-only until activation.
- Shadow output must remain attributable to the candidate and baseline versions being compared.

### Candidate-Versus-Active Comparison Report

The control plane should persist a structured comparison artifact before activation.

| Comparison section | Contents |
|---|---|
| Run quality | Success rate, terminal reasons, retry counts, and average completion time |
| Safety | Policy violations, forbidden-path attempts, and escalation differences |
| Cost | Model usage, token totals, provider failovers, and budget deltas |
| Artifact fidelity | Planner artifact completeness and readiness-gate outcomes |

Gating logic:

- Candidate activation is automatically blocked when success rate falls below the configured threshold, cost exceeds configured tolerance, or safety regressions appear.
- Operator overrides require a written rationale stored with the comparison report.

### Rollback And Snapshot Retention

Rollback changes the active version for future runs only.

| State | Rule |
|---|---|
| New runs | Resolve against the newly activated or rolled-back snapshot |
| Active runs | Keep their pinned snapshot until terminal completion |
| Paused runs | Resume against the same pinned snapshot even if it is no longer active |
| Snapshot cleanup | Allowed only after no non-terminal run references the snapshot |

Rollback rules:

- Rollback creates a new audit event even when it reactivates an older version.
- Snapshot retention logic must account for paused, shadow, and DLQ-resumable runs.

## Verification Fixtures

| Task | Fixture definition | Expected proof |
|---|---|---|
| 4.1 Invalid graph rejection | Submit graphs that compile technically but omit readiness, tester, reviewer, pre-PR sync, or escalation coverage. | Validation rejects the candidate despite successful compilation. |
| 4.2 Shadow validation | Execute a candidate config in shadow mode with write-capable handlers present but read-only isolation enabled. | Queue, credential, worker, and application layers keep the run read-only and produce persisted comparison evidence. |
| 4.3 Rollback and retention validation | Activate a new config while runs are active and paused, then roll back. | Only new runs pick up the rollback, while existing runs keep their pinned snapshots and referenced snapshots remain available. |

These fixtures drive later phases:

- Phase 6 binds the graph editor, agent forms, and activation UX to these backend contracts.
- Phase 7 promotes config validation, shadow evidence, and rollback behavior into release and operational acceptance criteria.

## Implementation Slice

This phase now includes a contract-level backend control-plane slice under `backend/src/backend/control_plane/` plus test coverage in `backend/tests/test_control_plane_contracts.py`.

Implemented modules:

- `graph.py` defines typed graph configs, handler references, compile-time checks, PR-path invariant validation, repo-write gate validation, and escalation-sink coverage checks.
- `agents.py` validates role-bound agent configs against model-catalog entries, runtime tool allowlists, retry settings, and dry-run tool requests.
- `shadow.py` models defense-in-depth read-only shadow isolation and produces candidate-versus-active comparison reports that can block activation.
- `store.py` implements in-memory version records, audit events, activatable snapshots, run-to-snapshot pinning, rollback, and snapshot cleanup rules for non-terminal runs.

Implementation boundaries:

- The slice is intentionally in-memory so the product can exercise the control-plane contracts before PostgreSQL-backed persistence and admin APIs are introduced.
- The graph validator enforces safety invariants even when a candidate graph compiles technically, matching the protected `ticket_to_pr_v1` profile rules.
- Activation and rollback operate on versioned snapshot records for new runs only, while active and paused runs retain their pinned snapshot until they become terminal.
