## ADDED Requirements

### Requirement: Admission Flip From Audit To Enforce Requires Fresh Evidence

The admission policy flip from `Audit` to `Enforce` SHALL require fresh ephemeral K3s integration evidence and fresh air-gapped bundle verification evidence. The flip SHALL produce a signed manifest recording the consulted evidence hashes.

#### Scenario: Stale evidence blocks the flip
- **WHEN** an operator attempts to flip admission to `Enforce` and any required evidence is expired
- **THEN** the flip is rejected with the stale-evidence reason
- **AND** the rejection lists the expired evidence paths

#### Scenario: Successful flip produces a signed manifest
- **WHEN** the flip succeeds
- **THEN** a manifest is written with the active policy revision, evidence hashes, approving actor identities, and timestamp
- **AND** the manifest is referenced from the supply-chain runbook

### Requirement: Admission Drill Includes A Deliberate-Failure Variant

The ephemeral K3s integration drill SHALL include a variant that deploys an unsigned image and asserts the policy rejects it. A drill that does not exercise the rejection path SHALL NOT count as fresh evidence.

#### Scenario: Drill missing the rejection variant fails freshness check
- **WHEN** a drill run does not include the unsigned-image rejection step
- **THEN** the run is recorded with status `incomplete`
- **AND** the freshness check refuses to count it
