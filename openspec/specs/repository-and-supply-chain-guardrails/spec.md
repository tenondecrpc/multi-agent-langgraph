# repository-and-supply-chain-guardrails Specification

## Purpose
TBD - created by archiving change phase-3-tenant-security-and-access. Update Purpose after archive.
## Requirements
### Requirement: Repository Safety Rails Are Mandatory

The product MUST block unsafe repository actions through backend-enforced path and branch controls.

#### Scenario: Forbidden path writes are blocked
- **WHEN** an agent attempts to modify protected branches or protected file classes such as CI config, infra, Dockerfiles, secrets, or CODEOWNERS-class files
- **THEN** the action is blocked or escalated through a registered security path
- **AND** the product does not treat the change as a normal candidate for automatic PR creation

#### Scenario: Missing branch protection blocks PR creation
- **WHEN** the target repository lacks the required server-side branch protection for the planned base branch
- **THEN** PR creation is refused
- **AND** the run escalates with an explicit policy reason

### Requirement: Secret Hygiene Is Enforced End-To-End

Secret scanning MUST run across developer, runtime, and CI surfaces relevant to generated changes.

#### Scenario: Secret finding halts the run
- **WHEN** generated diffs, PR text, or relevant repository artifacts contain a secret-scanner finding
- **THEN** the run halts normal progress and escalates
- **AND** the secret-bearing output is not forwarded as if it were safe

### Requirement: Signed And Transparent Authorship Is Required

Agent-authored commits and deliverables MUST support signed provenance and transparent authorship metadata.

#### Scenario: Unsigned commit is not accepted
- **WHEN** the product prepares a commit for an automated change
- **THEN** the commit is expected to use the configured signing mechanism
- **AND** downstream branch protection may reject unsigned commits without weakening the product contract

#### Scenario: PR provenance stays visible
- **WHEN** a PR is prepared by the system
- **THEN** the PR includes standardized generated-by provenance metadata that links the change to the responsible run

### Requirement: Supply-Chain Controls Are Baseline Requirements

The product MUST plan for SBOM generation, image signing, provenance, dependency scanning, and license policy enforcement.

#### Scenario: Build artifacts carry security evidence
- **WHEN** images or release artifacts are produced later in the implementation lifecycle
- **THEN** the build pipeline produces SBOM and provenance evidence and signs the result
- **AND** downstream environments can verify the signed artifacts before promotion

#### Scenario: Vulnerability and license policy remain enforceable
- **WHEN** dependencies or base images are evaluated in CI
- **THEN** the pipeline can block high-risk vulnerabilities and disallowed licenses according to policy
- **AND** pinned or reproducible build requirements are not optional

### Requirement: Branch-Protection Verification Is Composed With Existing Guards

The branch-protection verification SHALL run as part of the pre-PR chain together with implementation, tests, diff-size guard, forbidden-path guard, review approval, and pre-PR sync. Order and atomicity of these guards SHALL NOT be bypassable.

#### Scenario: Any missing guard blocks PR creation
- **WHEN** any of the guards (implementation, tests, diff-size, forbidden-path, review approval, pre-PR sync, branch-protection) is not satisfied
- **THEN** the pr_creator node does not open a PR
- **AND** the run escalates via its registered sink

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
