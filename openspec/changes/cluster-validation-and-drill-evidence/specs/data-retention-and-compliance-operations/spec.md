## ADDED Requirements

### Requirement: GDPR Tenant Erasure Drill Runs Quarterly With Evidence

A GDPR tenant erasure drill SHALL run quarterly on a synthesized tenant. The drill SHALL exercise the cascade across all retention-governed tables and SHALL produce a structured evidence bundle.

#### Scenario: Quarterly erasure drill verifies cascade
- **WHEN** the drill runs
- **THEN** the post-drill assertion confirms the synthesized tenant has zero rows in every cascade-governed table
- **AND** the evidence bundle records the per-table row counts before and after

### Requirement: Erasure Drill Includes A Deliberate-Failure Variant

The drill SHALL include a variant that deliberately omits one cascade table and asserts the post-drill check detects the omission.

#### Scenario: Omitted table is detected
- **WHEN** the drill skips a cascade table
- **THEN** the post-drill assertion fails with the missing-table reason
- **AND** the drill is recorded as a successful detection
