# ticket-execution-state Specification

## Purpose
TBD - created by archiving change phase-1-runtime-sdd-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Stable Run Identity And Config Pinning

Every accepted execution MUST receive a unique `run_id` and `thread_id`, while the business identity remains the Jira `ticket_key`.

#### Scenario: New webhook creates a new execution identity
- **WHEN** a valid webhook is accepted for a ticket
- **THEN** the system creates a fresh `run_id`
- **AND** derives `thread_id` from `tenant_id`, `ticket_key`, and `run_id`
- **AND** pins the config snapshot used for the run at acceptance time

#### Scenario: Resume keeps the same execution identity
- **WHEN** a paused run is resumed after an interrupt or transient failure
- **THEN** the workflow reuses the same `run_id`, `thread_id`, and pinned config snapshot
- **AND** it does not silently switch to the latest active config version

### Requirement: Checkpoint-Compatible Ticket State

The ticket state MUST persist the runtime artifacts, retry counters, review state, merge guard state, and escalation metadata needed to resume from any checkpoint boundary.

#### Scenario: State supports retry and resume
- **WHEN** a run pauses after planner, coder, tester, reviewer, or pre-PR sync work
- **THEN** the stored state includes the latest artifact summaries, retry counters, approval metadata, and guarded-flow markers needed for deterministic continuation

#### Scenario: Config compatibility is protected
- **WHEN** a non-terminal run references a config snapshot or handler contract
- **THEN** that referenced snapshot remains available for the lifetime of the run
- **AND** garbage collection or rollback routines do not remove the referenced runtime contract prematurely

### Requirement: Memory And Checkpoint Separation

Checkpoint state and long-term memory MUST remain separate persisted concerns even when they share the same PostgreSQL control plane.

#### Scenario: Checkpoint state remains per execution
- **WHEN** state is stored for a run
- **THEN** resumable execution state is keyed by the current `thread_id`
- **AND** it is not reused by a later accepted run for the same ticket

#### Scenario: Long-term memory remains namespaced
- **WHEN** long-term memory is stored or queried
- **THEN** it is namespaced by tenant and repository scope, with ticket-level context where applicable
- **AND** it remains distinct from checkpoint state used for exact resume semantics

### Requirement: Run Repository Is Backed By PostgreSQL And LangGraph PostgresSaver

The run repository SHALL persist ticket run state, escalation bindings, and pause/resume transitions in PostgreSQL using the LangGraph PostgresSaver for checkpoint rows and a tenant-scoped `runs` table for high-level state. No process-local authoritative copy of run state MAY exist on the success path.

#### Scenario: Run state survives pod restart
- **WHEN** a ticket run is in-flight and its worker pod is killed
- **THEN** another worker resumes the run from the latest persisted checkpoint using the same `run_id` and `thread_id`
- **AND** the pinned config snapshot remains intact

#### Scenario: Pause and resume write through to PostgreSQL atomically
- **WHEN** a run pauses on an escalation
- **THEN** the status, `paused_at_node`, `escalation_reason`, and `escalation_sink` are committed in a single transaction with the checkpoint
- **AND** a subsequent resume reads exactly that state without relying on any in-process cache

### Requirement: Run Data Is Tenant-Scoped At The Storage Layer

Every row in the `runs` table SHALL carry `tenant_id` and `team_id` and SHALL be protected by PostgreSQL row-level security keyed to the session tenant GUC.

#### Scenario: Cross-tenant run access is blocked at the database
- **WHEN** a session with tenant A queries a run belonging to tenant B
- **THEN** the query returns zero rows
- **AND** the application surfaces a typed authorization error consistent with the rest of the tenant-isolation surface

