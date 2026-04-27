## ADDED Requirements

### Requirement: GDPR Tenant Erasure Drill Runs Quarterly With Evidence

A GDPR tenant erasure drill SHALL run quarterly on a synthesized tenant. The drill SHALL exercise the cascade across all retention-governed tables and SHALL produce a structured evidence bundle.

The synthesized tenant SHALL be created from deterministic fixtures and SHALL be marked as drill-only in metadata. The drill SHALL cover checkpoints, memory, metering, audit references, DLQ records, webhook idempotency records, configuration snapshots, budget records, provider health references, and any tenant-scoped tables introduced by later migrations. Evidence SHALL include per-table row counts before and after erasure, retained audit exceptions, bounded retention exceptions, approver identities, and confirmation that no real customer tenant identifier was targeted.

#### Scenario: Quarterly erasure drill verifies cascade
- **WHEN** the drill runs
- **THEN** the post-drill assertion confirms the synthesized tenant has zero rows in every cascade-governed table
- **AND** the evidence bundle records the per-table row counts before and after

#### Scenario: Real tenant target is rejected
- **WHEN** an erasure drill is configured with a tenant identifier that is not marked drill-only
- **THEN** the drill refuses to run
- **AND** a SEV2 internal incident is opened because destructive-drill guardrails were violated

### Requirement: Erasure Drill Includes A Deliberate-Failure Variant

The drill SHALL include a variant that deliberately omits one cascade table and asserts the post-drill check detects the omission.

#### Scenario: Omitted table is detected
- **WHEN** the drill skips a cascade table
- **THEN** the post-drill assertion fails with the missing-table reason
- **AND** the drill is recorded as a successful detection

### Requirement: Compliance Evidence Retention Is Auditable

Tenant erasure drill evidence SHALL be retained for at least the quarterly evidence validity window and for the repository's configured compliance evidence retention period when longer. The evidence SHALL link to the DPA and retention runbook references used by operators, and SHALL record whether any bounded retention exceptions remain after erasure. Expired or unsigned evidence SHALL NOT be used to support a compliance claim.

#### Scenario: Compliance reviewer inspects erasure evidence
- **WHEN** a reviewer opens the quarterly erasure evidence bundle
- **THEN** the bundle lists the synthesized tenant, table coverage, before and after counts, bounded retention exceptions, approvers, and signed timestamp
- **AND** every retained exception links to an auditable rationale
