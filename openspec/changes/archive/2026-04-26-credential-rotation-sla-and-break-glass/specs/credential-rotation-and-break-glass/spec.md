## ADDED Requirements

### Requirement: 90-Day Default Credential Rotation SLA

Every stored credential SHALL have a `next_rotation_due` at most 90 days from last rotation. Credentials within 14 days of due SHALL raise warning alerts; overdue credentials SHALL block ticket acceptance for their tenant and team scope.

#### Scenario: Overdue credential blocks new runs
- **WHEN** a credential is past `next_rotation_due`
- **THEN** ticket acceptance for its scope fails closed with a typed error
- **AND** an alert is active until rotation completes

### Requirement: Dual-Control Break-Glass

Break-glass access SHALL require approval from two distinct super_admins, SHALL be time-bounded, and SHALL emit immutable audit evidence.

#### Scenario: Single approver cannot activate a grant
- **WHEN** only one super_admin has approved a break-glass request
- **THEN** the grant is not active
- **AND** no elevated operations succeed against it

#### Scenario: Grant expiration revokes access
- **WHEN** a grant reaches `expires_at`
- **THEN** elevated operations fail and a revocation audit row is written

### Requirement: Staged KEK Rotation With Dual-Read

KEK rotation SHALL proceed in stages: introduce new KEK, enable dual-read for old- and new-wrapped DEKs, re-wrap in background, switch default, retire old KEK. Readers SHALL successfully decrypt rows wrapped by either the previous or the current default during the rotation window.

#### Scenario: Pod restart mid-rotation is safe
- **WHEN** a worker restarts while the re-wrap job is running
- **THEN** the job resumes from its checkpoint
- **AND** no ciphertext row is left un-decryptable

### Requirement: Quarterly Drill Produces Evidence

A quarterly in-cluster drill Job SHALL run the full staged rotation against a dedicated test tenant and SHALL publish an evidence bundle to the status page.

#### Scenario: Drill failure raises an incident
- **WHEN** the drill Job fails
- **THEN** an alert fires with the drill log link
- **AND** the status page reflects the failed drill until remediation
