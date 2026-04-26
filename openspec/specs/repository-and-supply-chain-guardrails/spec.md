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
