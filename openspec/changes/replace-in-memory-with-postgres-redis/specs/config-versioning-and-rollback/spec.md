## ADDED Requirements

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
