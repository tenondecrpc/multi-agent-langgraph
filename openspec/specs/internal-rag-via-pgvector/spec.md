# internal-rag-via-pgvector Specification

## Purpose
TBD - created by archiving change optional-internal-rag-via-pgvector. Update Purpose after archive.
## Requirements
### Requirement: Capability Is Feature-Flagged And Default Off

Internal RAG SHALL be gated by the `internal_rag_enabled` feature flag with default OFF. Enabling the flag without `pgvector` available SHALL fail closed at boot.

#### Scenario: Flag on without pgvector fails boot
- **WHEN** the flag is enabled but the `pgvector` extension is not present
- **THEN** readiness fails with a structured error
- **AND** ticket acceptance is refused for that tenant

### Requirement: Tenant-Scoped Knowledge Base With Row-Level Security

Knowledge documents and chunks SHALL be tenant-scoped and SHALL be protected by PostgreSQL row-level security keyed to the session tenant GUC. Cross-tenant retrieval SHALL be impossible.

#### Scenario: Cross-tenant query returns nothing
- **WHEN** a session with tenant A issues a retrieval that would match tenant B rows
- **THEN** the query returns zero rows
- **AND** a typed authorization error surfaces if explicitly attempted

### Requirement: Read-Only Retrieval During Ticket Execution

Retrieval during a ticket run SHALL be strictly read-only. Ingestion SHALL happen only via the admin API outside of ticket execution.

#### Scenario: Ticket execution attempts ingestion
- **WHEN** any runtime agent attempts a write to the knowledge tables
- **THEN** the write is refused with a typed error
- **AND** an audit event records the attempt

### Requirement: Role Whitelist For Retrieval

Only planner and reviewer roles SHALL be permitted to call retrieval during ticket execution. Coder and pr_creator SHALL be denied.

#### Scenario: Coder retrieval is denied
- **WHEN** the coder agent calls retrieval
- **THEN** the call fails with a typed permission error
- **AND** the violation is observable

### Requirement: Retrieved Excerpts Persist In Run State

Every retrieval during a run SHALL persist a summary (chunk ids, distance, truncated text) into the run state so behavior is reproducible and auditable.

#### Scenario: Resume reuses persisted excerpts
- **WHEN** a paused run resumes
- **THEN** the previously retrieved excerpts are available in state
- **AND** the agent does not silently re-query with different parameters

### Requirement: Air-Gapped Works Without Vendor Embeddings

In the air-gapped profile, embeddings SHALL come from a self-hosted endpoint configured via Helm. No vendor embedding endpoint SHALL be called.

#### Scenario: Air-gapped ingestion uses internal embeddings
- **WHEN** ingestion runs in air-gapped mode
- **THEN** the embedding call targets the in-cluster endpoint
- **AND** NetworkPolicy denies any accidental egress

### Requirement: Admin Dry-Run Search

The admin API SHALL expose a dry-run search endpoint restricted to operators for testing retrieval without triggering ticket execution.

#### Scenario: Operator tests retrieval quality
- **WHEN** an operator calls the dry-run endpoint
- **THEN** results are returned for inspection
- **AND** no ticket run is created or modified

