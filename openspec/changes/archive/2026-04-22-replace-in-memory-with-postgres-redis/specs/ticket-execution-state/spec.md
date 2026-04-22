## ADDED Requirements

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
