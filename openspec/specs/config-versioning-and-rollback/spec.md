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

