# config-versioning-and-rollback Specification

## Purpose
TBD - created by archiving change phase-5-config-driven-graph-and-admin-control. Update Purpose after archive.
## Requirements
### Requirement: Runtime Config Is Versioned In PostgreSQL

Graph and agent configuration MUST be stored as versioned, auditable records in PostgreSQL.

#### Scenario: Config change creates a new version
- **WHEN** an admin updates graph or agent configuration
- **THEN** the change is stored as a new versioned record with audit metadata
- **AND** prior versions remain available for rollback and historical inspection

### Requirement: Activation Applies Only To New Runs

A newly activated config version MUST affect only runs accepted after activation, while active or paused runs keep their pinned snapshot.

#### Scenario: In-flight run keeps old snapshot
- **WHEN** a config version changes while a run is active or paused
- **THEN** the existing run continues against its pinned config snapshot
- **AND** the system does not hot-swap the run onto the newly activated topology

### Requirement: Rollback Is First-Class

Operators MUST be able to revert to a prior known-good config version without losing auditability.

#### Scenario: Rollback reactivates prior version
- **WHEN** an operator triggers a config rollback
- **THEN** the prior version becomes the active candidate for new runs
- **AND** the rollback action is audited with actor and rationale

#### Scenario: Referenced snapshots remain available
- **WHEN** a config version is no longer active but is still pinned by a non-terminal run
- **THEN** the system retains that version until the referencing runs no longer require it
- **AND** cleanup does not invalidate resumability

### Requirement: Control-Plane Config Lives In PostgreSQL Tables With Optimistic Concurrency

Graph versions, agent versions, snapshots, run-snapshot bindings, shadow reports, and audit events SHALL be stored in dedicated PostgreSQL tables. Activations and rollbacks SHALL be transactional. Audit events SHALL be append-only and indexed by `(target_id, created_at)`.

#### Scenario: Two concurrent activations do not interleave
- **WHEN** two operators attempt to activate different snapshots concurrently
- **THEN** one transaction succeeds and the other fails with a typed conflict error
- **AND** the audit log reflects exactly the winning activation

#### Scenario: Rollback restores the prior active snapshot atomically
- **WHEN** an operator triggers a rollback
- **THEN** the previously active snapshot becomes active in a single transaction with an audit event
- **AND** run-snapshot bindings for non-terminal runs retain their pinned snapshot

### Requirement: Audit Events Are Append-Only And Retained

The `audit_events` table SHALL enforce append-only semantics at the schema or role level. Retention SHALL match the data-retention policy and SHALL NOT permit silent deletion.

#### Scenario: Update or delete on audit is rejected
- **WHEN** any role attempts to update or delete an audit event
- **THEN** the database rejects the operation
- **AND** the attempt is logged and alertable

