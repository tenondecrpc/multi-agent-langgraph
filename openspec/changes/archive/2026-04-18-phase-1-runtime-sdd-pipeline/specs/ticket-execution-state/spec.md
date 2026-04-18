## Non-Goals

- Declaring database table layouts or migration steps.
- Defining observability metrics or dashboard fields.
- Defining tenant auth or credential encryption behavior.

## ADDED Requirements

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
