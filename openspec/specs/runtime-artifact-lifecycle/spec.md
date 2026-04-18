# runtime-artifact-lifecycle Specification

## Purpose
TBD - created by archiving change phase-1-runtime-sdd-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Planner-Owned Runtime Artifact Chain

The runtime ticket pipeline MUST create and persist planner-owned SDD artifacts in the canonical order `constitution -> feature_spec -> clarification_notes -> implementation_plan -> task_list` before repo-writing behavior is allowed.

#### Scenario: Artifact chain is created before implementation
- **WHEN** a ticket run enters the planning portion of the workflow
- **THEN** the planner produces the constitution-derived feature specification, clarification notes, implementation plan, and task list in sequence
- **AND** each artifact is persisted in checkpoint-compatible state so retries, reviews, and resumes operate on the same pinned artifacts

#### Scenario: Runtime and build-time SDD remain separate
- **WHEN** runtime artifacts are created for a ticket
- **THEN** they are persisted in runtime state and checkpoints
- **AND** they are not committed into `openspec/` or treated as build-time OpenSpec artifacts for this repository

### Requirement: Repo-Write Gate

Repo-writing nodes and actions MUST NOT run unless `spec_ready_for_implementation` is true and a task list exists for the active run.

#### Scenario: Repo-writing is blocked before readiness
- **WHEN** a coder or any other repo-writing step is reached before the planner has marked the spec ready
- **THEN** the workflow blocks the repo-writing step
- **AND** the run is routed back to planning or escalation instead of mutating the repository

#### Scenario: Repo-writing remains gated after replanning
- **WHEN** review or clarification forces a replan after a prior task list existed
- **THEN** the workflow requires the refreshed plan and task list to be persisted again
- **AND** repo-writing remains blocked until the refreshed artifacts satisfy the same readiness gate

### Requirement: Autonomous Clarification With Break-Glass Escalation

The normal success path MUST remain autonomous-first, while unresolved ambiguity MAY escalate to a human only on registered exception paths.

#### Scenario: Ambiguity is resolved autonomously within limits
- **WHEN** the planner or reviewer identifies ambiguity and the configured clarification iteration budget has not been exhausted
- **THEN** the workflow loops through autonomous clarification and artifact refinement
- **AND** the success path does not pause for manual approval

#### Scenario: Ambiguity escalates after limits are reached
- **WHEN** unresolved ambiguity remains after the maximum autonomous clarification iterations
- **THEN** the run pauses on a registered escalation path with explicit unresolved questions
- **AND** the escalation reason is persisted in state and audit context

#### Scenario: Single-pass clarification is used as a Tier 2 degradation
- **WHEN** the deployment intentionally ships the documented Tier 2 degradation path for clarification
- **THEN** the runtime may collapse clarification to a single pass
- **AND** the repo-write gate, mandatory tests, mandatory review, and break-glass-only human approval rules remain unchanged

### Requirement: Task List Declares Test And Quality Targets

The planner-owned `task_list` MUST declare the unit tests, end-to-end tests, and code-quality checks required for the ticket before `spec_ready_for_implementation` becomes true.

#### Scenario: Implementation tasks carry paired test tasks
- **WHEN** the planner emits an implementation task that modifies production logic
- **THEN** the same task list includes a paired unit-test task that names the target behavior to cover
- **AND** `spec_ready_for_implementation` does not become true while any implementation task lacks its paired test task

#### Scenario: User-facing changes declare end-to-end coverage
- **WHEN** the planner identifies that the ticket changes a public API, webhook, UI surface, or cross-service flow
- **THEN** the task list includes an end-to-end test task that exercises that surface
- **AND** the runtime persists the declared test and quality targets so the tester, reviewer, and PR creator nodes consume the same pinned checklist

