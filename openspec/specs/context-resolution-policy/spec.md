# context-resolution-policy Specification

## Purpose
TBD - created by archiving change phase-1-runtime-sdd-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Local-First Context Resolution Order

Runtime agents MUST resolve context in a consistent order: Jira, repository, run-state and memory, optional internal knowledge, first-party APIs, and external research last.

#### Scenario: Planner resolves context in the required order
- **WHEN** the planner starts work on a ticket
- **THEN** it consumes Jira and repository context before consulting first-party APIs or external research
- **AND** it uses external research only when the earlier sources are insufficient to proceed reliably

#### Scenario: Reviewer follows the same policy
- **WHEN** the reviewer validates implementation against the plan and ticket context
- **THEN** it reuses the same local-first resolution order
- **AND** it does not bypass repository or checkpoint context in favor of external sources

### Requirement: Optional Internal Knowledge Retrieval Remains Tenant-Scoped

The optional internal knowledge path MAY use `pgvector` in PostgreSQL, but it MUST remain tenant-scoped, read-only during ticket execution, and disabled by default unless explicitly enabled.

#### Scenario: Internal knowledge is enabled
- **WHEN** a tenant enables internal knowledge retrieval
- **THEN** planner and reviewer queries are filtered by tenant and allowed scope before semantic ranking
- **AND** retrieved excerpts are summarized into runtime state so retries and reviews can use the same pinned context

#### Scenario: Internal knowledge stays within PostgreSQL
- **WHEN** internal knowledge retrieval is enabled
- **THEN** embeddings and chunk metadata are stored in PostgreSQL with `pgvector`
- **AND** the feature does not introduce a new production datastore

### Requirement: Role-Bounded Context Access

Each runtime role MUST only access the context sources appropriate for its least-privilege boundary.

#### Scenario: Research access stays bounded
- **WHEN** the planner or reviewer needs additional context
- **THEN** they may consult the configured knowledge and research surfaces allowed for their role
- **AND** coder, tester, and PR creator remain constrained to their narrower operational boundaries

#### Scenario: Retrieved context is treated as data
- **WHEN** external or semi-trusted material is introduced into prompts or summaries
- **THEN** the runtime treats it as untrusted data rather than executable instructions
- **AND** later security phases may strengthen this handling without weakening the local-first order

