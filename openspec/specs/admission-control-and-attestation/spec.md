# admission-control-and-attestation Specification

## Purpose

Cluster-side signature and provenance verification, policy exceptions flow, emergency break-glass with audited rationale. Created by archiving change supply-chain-and-admission-controller.

## Requirements

### Requirement: Unsigned Or Unattested Images Are Rejected At Admission

The cluster SHALL reject any workload image that lacks a valid cosign signature and an attached SLSA Level 3 provenance attestation. Digest-pinned references SHALL be required; `latest` tags SHALL be rejected.

#### Scenario: Missing signature blocks deploy
- **WHEN** a workload is applied with an image that is unsigned or has an invalid signature
- **THEN** the admission controller rejects it with an explanatory message
- **AND** the denial is observable per policy and per namespace

#### Scenario: Missing provenance blocks deploy
- **WHEN** a workload is applied with a signed image that lacks SLSA provenance
- **THEN** the admission controller rejects it
- **AND** an alert fires for the owning team

### Requirement: Policy Exceptions Are Audited And Time-Bounded

Any admission exception SHALL require a super_admin action, SHALL record actor, rationale, scope, and `expires_at`, and SHALL expire automatically.

#### Scenario: Exception auto-expires
- **WHEN** an exception reaches `expires_at`
- **THEN** the policy immediately reverts to enforcing
- **AND** an audit row is written

### Requirement: Both Deployment Profiles Support Verification

The admission controller SHALL verify signatures and provenance in both connected and `air_gapped` profiles. Air-gapped verification SHALL NOT require outbound calls to vendor-operated endpoints.

#### Scenario: Air-gapped verification uses local trust roots
- **WHEN** the cluster runs in `air_gapped` profile
- **THEN** verification uses a mirrored Fulcio and Rekor or a pre-verified manifest bundle configured via Helm values
- **AND** no external network call is required at admission time
