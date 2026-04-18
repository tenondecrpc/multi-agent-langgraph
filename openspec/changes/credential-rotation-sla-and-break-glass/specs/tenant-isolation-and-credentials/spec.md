## ADDED Requirements

### Requirement: Credentials Carry Rotation Metadata And Support Dual-Read

Every stored credential row SHALL carry `rotated_at`, `next_rotation_due`, and a KEK version reference so dual-read decryption during KEK rotation is deterministic.

#### Scenario: Read succeeds under both KEK versions during rotation
- **WHEN** a row is wrapped under the previous KEK and another under the new KEK
- **THEN** both rows decrypt successfully during the dual-read window
- **AND** a metric distinguishes reads per KEK version
