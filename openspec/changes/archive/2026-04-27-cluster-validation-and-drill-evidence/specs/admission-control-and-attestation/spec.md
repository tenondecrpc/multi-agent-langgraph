## ADDED Requirements

### Requirement: Admission Flip From Audit To Enforce Requires Fresh Evidence

The admission policy flip from `Audit` to `Enforce` SHALL require fresh ephemeral K3s integration evidence and fresh air-gapped bundle verification evidence. The flip SHALL produce a signed manifest recording the consulted evidence hashes.

The gate SHALL require:

- Fresh `ephemeral-k3s-admission-integration` evidence for the target policy revision.
- Fresh `air-gapped-bundle-verification` evidence when the deployment profile is `air_gapped` or when the policy depends on mirrored trust roots.
- Passing deliberate-failure evidence proving unsigned or unattested images are rejected.
- No open SEV1 or SEV2 incident against supply-chain signing, provenance, admission enforcement, or bundle verification.
- Dual-control approval when the flip changes a customer-facing environment from `Audit` to `Enforce`.

The signed flip manifest SHALL be written to `docs/drills/evidence/admission-flips/<run-id>/manifest.json` and signed with the same evidence signing mechanism used by drill bundles. It SHALL include `schema_version`, `run_id`, `policy_name`, `policy_revision`, `from_mode`, `to_mode`, `target_profile`, `target_cluster`, `evidence_hashes`, `approvers`, `created_at`, `git_sha`, `workflow_run_url`, `signature_ref`, and `rollback_to_mode`.

#### Scenario: Stale evidence blocks the flip
- **WHEN** an operator attempts to flip admission to `Enforce` and any required evidence is expired
- **THEN** the flip is rejected with the stale-evidence reason
- **AND** the rejection lists the expired evidence paths

#### Scenario: Successful flip produces a signed manifest
- **WHEN** the flip succeeds
- **THEN** a manifest is written with the active policy revision, evidence hashes, approving actor identities, and timestamp
- **AND** the manifest is referenced from the supply-chain runbook

#### Scenario: Open SEV2 blocks the flip
- **WHEN** a SEV2 incident is open for supply-chain signing, provenance, admission enforcement, or bundle verification
- **THEN** the admission flip is rejected with reason `blocking_incident_open`
- **AND** the rejection links the incident identifier

### Requirement: Admission Drill Includes A Deliberate-Failure Variant

The ephemeral K3s integration drill SHALL include deliberate-failure variants that deploy an unsigned image, deploy a signed image without SLSA provenance, and deploy an image with a mutable tag. The drill SHALL assert the policy rejects each invalid workload in both connected and `air_gapped` verification modes where applicable. A drill that does not exercise the rejection path SHALL NOT count as fresh evidence.

#### Scenario: Drill missing the rejection variant fails freshness check
- **WHEN** a drill run does not include the unsigned-image rejection step
- **THEN** the run is recorded with status `incomplete`
- **AND** the freshness check refuses to count it

#### Scenario: Air-gapped admission drill avoids vendor egress
- **WHEN** the admission drill runs in `air_gapped` mode
- **THEN** signature and provenance verification use mirrored Fulcio and Rekor or a pre-verified manifest bundle
- **AND** the evidence records that no external vendor endpoint was contacted

### Requirement: Admission Flip Rolls Back When Evidence Is Invalidated

If evidence used for an `Audit` to `Enforce` flip is later invalidated, expires, is tampered with, or is tied to a drill that is found incomplete, the system SHALL automatically block further flips, open a SEV2 internal incident, and roll the policy mode back to `Audit` for affected non-production environments. For production environments, rollback to `Audit` SHALL require dual-control approval unless the admission controller cannot safely verify signatures or provenance, in which case the documented break-glass path applies.

The rollback record SHALL reference the original flip manifest, invalidated evidence paths, affected policy revision, actor or automation that initiated rollback, and the follow-up incident.

#### Scenario: Evidence tampering invalidates enforce state
- **WHEN** evidence used by an `Enforce` flip fails signature validation after the flip
- **THEN** the admission gate marks the evidence invalid
- **AND** a SEV2 incident opens with the original flip manifest and rollback action

#### Scenario: Non-production policy returns to Audit
- **WHEN** a staging admission flip is invalidated by expired or tampered evidence
- **THEN** the policy mode rolls back to `Audit`
- **AND** the rollback manifest records the affected evidence hashes
