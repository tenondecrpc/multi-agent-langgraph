## ADDED Requirements

### Requirement: CI Generates SBOM, Signature, And Provenance Per Image

Every image built in CI SHALL have a syft SBOM attached, a cosign keyless signature bound to the CI OIDC identity, and a SLSA Level 3 provenance attestation.

#### Scenario: Missing any artifact fails the build
- **WHEN** an image is pushed without an SBOM, signature, or provenance
- **THEN** CI fails with an actionable error
- **AND** the image is not promotable

### Requirement: Dependency Scanning Blocks Critical And High Findings

Trivy, Grype, and OSV-Scanner SHALL run in CI and block on critical and high severities. Allowlisted findings SHALL require rationale, actor, and `expires_at`.

#### Scenario: Unreviewed high finding blocks merge
- **WHEN** a scan reports a high finding not on the allowlist
- **THEN** the merge is blocked
- **AND** the report is attached to the PR

### Requirement: Dockerfile Pinning And No Latest Tag

Base images in Dockerfiles SHALL be pinned by digest. The `latest` tag SHALL NOT appear in any Dockerfile or Helm value.

#### Scenario: Dockerfile lint rejects floating tag
- **WHEN** a Dockerfile references a mutable or `latest` tag
- **THEN** CI lint fails
- **AND** the operator receives a remediation hint

### Requirement: License Allowlist And Secret Scanning In CI

Every merged commit SHALL pass license allowlist enforcement and secret scanning with gitleaks and trufflehog.

#### Scenario: Disallowed license fails PR checks
- **WHEN** a dependency introduces a license outside the allowlist
- **THEN** the PR check fails
- **AND** the remediation path is documented in the error
