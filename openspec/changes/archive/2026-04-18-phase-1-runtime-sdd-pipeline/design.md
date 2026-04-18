## Context

This phase extracts the product's runtime SDD backbone from `docs/PLAN.md`. The goal is to make the artifact chain, state contract, context policy, and guarded ticket flow explicit before the repository plans infrastructure, security, or frontend work in deeper slices.

## Goals / Non-Goals

**Goals:**
- Define the planner-owned artifact lifecycle as the only legal starting point for repo-writing behavior.
- Pin the execution identity, config snapshot rules, and checkpoint compatibility rules used across retries and resumes.
- Define the context resolution order so later phases do not invent competing lookup or research paths.
- Encode the protected success path and failure routing rules that every activatable workflow must preserve.

**Non-Goals:**
- Kubernetes topology, Helm structure, and sandbox hardening details.
- Authentication, RBAC, credential storage, and webhook security controls.
- LLM routing, budget reservations, metering, billing, and provider failover.
- Frontend, graph editor, and observability implementation details.

## Decisions

- The runtime artifact chain is modeled as a first-class product capability, not an implementation detail of the planner prompt.
- Repo-writing is guarded by two explicit state conditions: `spec_ready_for_implementation=true` and the presence of a task list.
- Clarification remains autonomous-first. Human approval is allowed only on registered exception paths after ambiguity cannot be resolved within configured bounds.
- Execution identity is split between the business identity (`ticket_key`) and the run identity (`run_id`), with the `thread_id` derived from the run identity so retries and resumes remain deterministic.
- Checkpoint state, long-term memory, and config snapshots remain distinct persisted concerns even when they are stored in the same PostgreSQL control plane.
- Context resolution follows a single local-first order: Jira, repo, run-state and memory, optional internal knowledge, first-party APIs, and external research last.
- The optional internal knowledge path must remain tenant-scoped, read-only during execution, and must reuse PostgreSQL with `pgvector` instead of introducing a new datastore.
- The protected success path always includes planner-owned SDD artifacts, implementation, tests, review, and pre-PR sync before PR creation.

## Risks / Trade-offs

- This phase is intentionally foundational, so weak wording here would leak ambiguity into every later phase.
- Some requirements reference later phases, which creates cross-phase coupling, but that coupling is preferable to allowing each later change to reinterpret the runtime contract.
- The full autonomous clarify loop is a Tier 2 GA target, so this phase must explicitly permit the single-pass degradation path without weakening the Tier 1 repo-write gate or break-glass rules.

## Implementation Slice

The first executable slice for this phase now lives under `backend/` and uses `uv` for dependency and command management.

- `backend/src/backend/runtime/models.py` implements the planner-owned artifacts, task-list readiness contract, run identity, and pause metadata.
- `backend/src/backend/runtime/context.py` implements the local-first context resolver with explicit provenance ordering.
- `backend/src/backend/runtime/planner.py` implements the rule-based constitution loader and planner artifact service used by the phase-1 workflow.
- `backend/src/backend/runtime/store.py` implements in-memory checkpoint persistence plus escalation sink validation and pause and resume helpers for tests.
- `backend/src/backend/runtime/workflow.py` implements the guarded LangGraph `StateGraph` that enforces readiness gating, bounded retries, pre-PR guards, and escalation routing.
- `backend/src/backend/app.py` exposes a minimal FastAPI surface for health checks and workflow simulation.
- `backend/tests/` covers the phase-1 repo-write gate, retry loops, review quality gate, escalation sink validation, context ordering, and identity-preserving pause and resume behavior.

## Runtime Flow Coverage

This phase covers the runtime flow declared in `docs/PLAN.md` without pulling in later platform, security, UI, or operations implementation detail.

| Runtime concern from `docs/PLAN.md` | Phase 1 contract outcome | Downstream extension point |
|---|---|---|
| Canonical artifact chain | `constitution -> feature_spec -> clarification_notes -> implementation_plan -> task_list` is the only legal path into repo-writing work. | Phase 5 may configure graph topology but may not remove this planner-owned prefix. |
| Repo-write gate | Repo mutation stays blocked until `spec_ready_for_implementation` is `true` and a persisted task list exists. | Phases 2, 3, and 5 add API, security, and config enforcement around the same gate. |
| Retry routing | Clarification, test, and review loops are bounded and checkpoint-compatible. | Phase 4 adds provider and budget pause reasons; phase 7 adds observability for the loops. |
| Escalation reasons | Every failure terminal path must map to an explicit reason and registered sink. | Phases 3, 4, 5, and 7 add security, budget, config, and incident sinks without redefining the reason model. |
| Mandatory guarded success path | Implementation, tests, review approval, and pre-PR sync remain mandatory before PR creation. | Phase 3 adds safety checks, phase 5 validates graph invariants, phase 7 adds release and quality gates. |
| Local-first context resolution | Jira, repository, run-state and memory, optional internal knowledge, first-party APIs, and external research last. | Phase 3 constrains access by role; phase 6 may visualize context outcomes but does not change lookup order. |

This coverage remains aligned with `openspec/config.yaml` and `AGENTS.md`:

- Tier 1 invariants preserved: repo-write gate, mandatory tests and review, break-glass-only interrupts, tenant-scoped state, and PostgreSQL-backed runtime persistence.
- Tier 2 degradation preserved: clarification may degrade to a documented single pass for GA, but the success path and protected guards do not change.
- Build-time and run-time SDD stay separate: these contracts describe per-ticket runtime artifacts and never authorize committing them into `openspec/`.

## Cross-Phase Contract Map

Later OpenSpec phases extend the runtime contract from this phase instead of redefining it:

| Later phase | Must inherit from phase 1 | Must not redefine |
|---|---|---|
| Phase 2 - platform and sandbox | API surfaces, worker shutdown, queue retry capture, sandbox checkpoint boundaries | Artifact ordering, repo-write readiness, escalation semantics |
| Phase 3 - tenant security and access | OIDC, RBAC, webhook verification, tool policy, forbidden-path enforcement | Context resolution order, planner ownership of artifacts, success-path ordering |
| Phase 4 - LLM governance and metering | Provider routing, budget reservations, failover pauses, usage attribution | Retry identity model, checkpoint lineage, planner-owned test declarations |
| Phase 5 - config-driven graph and admin control | Graph schema, activation, validation, rollback, shadow mode | Ability to bypass protected workflow invariants or replace the canonical planner prefix |
| Phase 6 - operator UI and control room | UI views, graph editing UX, sprite and accessibility behavior | Backend runtime contract, escalation meaning, or role boundaries |
| Phase 7 - observability, reliability, and release | Logs, traces, SLOs, HA/DR, CI and release gates | Runtime state meaning, repo-write gate, or required execution path |

## Backend Interface Plan

The future backend should express the runtime contract through explicit interfaces instead of prompt-only conventions.

### Planner-Owned Artifact Interfaces

```python
class RuntimeConstitutionLoader(Protocol):
    async def load_for_run(self, tenant_id: str, repo_id: str, config_snapshot_id: str) -> "RuntimeConstitution": ...


class PlannerArtifactService(Protocol):
    async def create_feature_spec(self, run: "TicketRunContext") -> "FeatureSpecArtifact": ...
    async def create_clarification_notes(self, run: "TicketRunContext") -> "ClarificationNotesArtifact": ...
    async def create_implementation_plan(self, run: "TicketRunContext") -> "ImplementationPlanArtifact": ...
    async def create_task_list(self, run: "TicketRunContext") -> "TaskListArtifact": ...
    async def mark_spec_ready(self, run_id: str, task_list_id: str, readiness_summary: str) -> "SpecReadiness": ...
```

Interface expectations:

- Constitution loading is snapshot-aware. It must resolve against the pinned config snapshot for the run, not the latest active configuration.
- Every planner artifact returns both structured fields and a human-readable summary so the same artifact can drive graph logic, review, and UI.
- `mark_spec_ready` is the only interface allowed to set `spec_ready_for_implementation=true`, and it must validate that the task list includes required test and quality targets.
- Planner artifacts are append-only within a run lineage. Replanning creates new artifact versions tied to the same `run_id`.

### Persisted Ticket State Model

The future state model must keep business identity, execution identity, and config identity distinct.

| Field group | Required fields | Purpose |
|---|---|---|
| Business identity | `tenant_id`, `team_id`, `repo_id`, `ticket_key` | Stable business scope and tenancy boundaries |
| Execution identity | `run_id`, `thread_id`, `accepted_at`, `accepted_by_surface` | Deterministic execution and resume semantics |
| Config pinning | `config_snapshot_id`, `graph_profile_id`, `agent_config_version`, `catalog_version` | Freeze runtime behavior for the lifetime of the run |
| Planner artifacts | `constitution_ref`, `feature_spec_ref`, `clarification_notes_ref`, `implementation_plan_ref`, `task_list_ref`, `spec_ready_for_implementation` | Drive repo-write readiness and downstream review |
| Retry and loop state | `clarification_attempts`, `test_retry_count`, `review_retry_count`, `replan_count`, `last_retry_reason` | Bound retries and explain transitions |
| Guard state | `diff_guard`, `merge_guard`, `required_test_targets`, `required_quality_checks`, `review_decision` | Enforce success-path gates before PR creation |
| Pause and escalation state | `paused_at_node`, `escalation_reason`, `escalation_sink`, `resume_requested_at`, `resume_token` | Pause, interrupt, and deterministic resume behavior |
| Audit context | `jira_event_id`, `trigger_trace_id`, `artifact_hashes`, `state_schema_version` | Auditable lineage and schema compatibility |

State rules:

- `thread_id` is derived from `tenant_id`, `ticket_key`, and `run_id`, and it never changes after acceptance.
- Resume and retry flows may mutate loop counters and guard state, but they may not replace `run_id`, `thread_id`, or `config_snapshot_id`.
- Review, diff, and merge guard markers must be persisted at checkpoint boundaries so restarts do not repeat a completed safety decision without traceability.

### Storage Contract Separation

Checkpoint state, long-term memory, and config snapshots may share PostgreSQL, but they remain separate contracts.

| Persisted concern | Scope and keying | Mutability | Audit expectation |
|---|---|---|---|
| Checkpoint state | `thread_id` scoped execution state | Mutable per node transition | Every checkpoint boundary records node name, transition reason, and state schema version |
| Long-term memory | Tenant, repository, and optional ticket namespace | Append-biased with retention rules | Memory writes record source, confidence, and retention window |
| Config snapshots | Versioned by control-plane activation | Immutable after pinning | Snapshot creation, activation, rollback, and access are all auditable |

Storage rules:

- Checkpoint garbage collection must never delete state referenced by a non-terminal run.
- Long-term memory must stay tenant-scoped and must not be reused as an exact resume mechanism.
- Config snapshots remain available until every run pinned to that snapshot reaches a terminal state.

## Guarded Flow Plan

### Graph Nodes And Route Functions

The future runtime graph should preserve a single protected success path:

`intake -> load_constitution -> create_feature_spec -> clarify -> create_plan -> create_task_list -> readiness_gate -> coder -> tester -> reviewer -> pre_pr_sync -> pr_creator`

Required routing functions:

- `route_after_clarification`: continues clarification while ambiguity remains and the configured clarification budget is available, otherwise escalates with `unresolved_ambiguity`.
- `route_after_readiness_gate`: routes to `coder` only when `spec_ready_for_implementation=true` and `task_list_ref` exists, otherwise returns to planning.
- `route_after_tester`: routes back to `coder` when required tests or quality checks fail and retry budget remains, otherwise escalates with `missing_or_failing_required_tests` or the concrete terminal reason.
- `route_after_reviewer`: routes to replanning or recoding when design checks fail and budget remains, otherwise escalates with `review_budget_exhausted`.
- `route_before_pr_creator`: enforces diff-size, forbidden-path, branch-protection, and merge-conflict guards before PR creation.

Required escalation reasons registered in this phase:

- `unresolved_ambiguity`
- `test_retry_budget_exhausted`
- `review_budget_exhausted`
- `missing_or_failing_required_tests`
- `diff_too_large`
- `merge_conflict_detected`
- `invalid_route_attempt`
- `missing_escalation_sink`

Every activation profile defined later must provide a sink mapping for each registered reason above before the graph can be considered valid.

### Context Resolution Implementation Contract

The future backend should centralize context lookup behind a resolver pipeline:

```python
class ContextResolver(Protocol):
    async def resolve(self, request: "ContextRequest") -> "ResolvedContextBundle": ...
```

Resolution stages, in order:

1. Jira ticket, comments, attachments, and linked issue metadata
2. Repository working tree, default branch metadata, and existing tests
3. Run-state artifacts, prior checkpoint summaries, and tenant-scoped memory
4. Optional internal knowledge in PostgreSQL with `pgvector`, read-only during execution
5. First-party APIs and documentation surfaces
6. External research only when all earlier stages are insufficient

Policy rules:

- Each stage emits provenance so downstream reviewers know which sources were actually used.
- External research must record the insufficiency reason from earlier stages.
- Coder, tester, and PR creator receive only the narrowed context they need and do not gain unrestricted research access.

### Clarification Degradation Toggle

The GA degradation path is a control-plane toggle, not a behavioral rewrite.

| Field | Allowed values | Rule |
|---|---|---|
| `clarification_mode` | `autonomous_loop`, `single_pass` | Default is `autonomous_loop`; `single_pass` is an allowed Tier 2 degradation only |
| `max_clarification_iterations` | integer >= 1 | Required for both modes so limits remain explicit |
| `ambiguity_escalation_reason` | registered enum | Must still escalate when ambiguity persists after the configured limit |

Even in `single_pass` mode:

- The planner must still produce the full artifact chain.
- The repo-write gate remains unchanged.
- Mandatory tests, review, and pre-PR sync remain unchanged.
- Human approval stays break-glass only.

## Verification Fixtures

Phase 1 validation should be executable later as automated fixtures and readable now as explicit contracts.

| Task | Fixture definition | Expected proof |
|---|---|---|
| 4.1 Repo-write gate | Construct a run with `task_list_ref=None` or `spec_ready_for_implementation=false` and attempt to enter `coder`. | Route is rejected and returned to planning or escalation without repository mutation. |
| 4.2 Resume identity | Pause a run after clarification, resume it, then retry after a test failure. | `run_id`, `thread_id`, and `config_snapshot_id` remain unchanged across both transitions. |
| 4.3 Escalation sink coverage | Enumerate all terminal routes and validate each reason against the registered sink map. | Validation fails if any terminal route lacks a reason or sink binding. |
| 4.4 Required test enforcement | Create a task list that declares unit and end-to-end targets, then simulate missing, skipped, and failing outcomes. | `pr_creator` remains unreachable until required targets pass or the run escalates with `missing_or_failing_required_tests`. |
| 4.5 Review quality gate | Provide a diff with passing tests but failing lint, type analysis, or declared SOLID-aligned checks. | Reviewer cannot approve; the run routes back within budget or escalates when the retry budget is exhausted. |

These fixtures should become the seed cases for later backend and CI suites:

- Phase 2 extends them with worker-drain and sandbox checkpoint tests.
- Phase 3 adds security and forbidden-path variants.
- Phase 5 validates graph-config compilation against the same invariant set.
- Phase 7 promotes them into CI and release gates for the product codebase.
