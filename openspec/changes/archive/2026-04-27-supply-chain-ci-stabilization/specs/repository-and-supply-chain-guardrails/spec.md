## ADDED Requirements

### Requirement: Stabilization Extends Existing Supply-Chain Guardrails

This change SHALL strengthen the existing `repository-and-supply-chain-guardrails` capability without reopening the prior supply-chain security decisions. The existing workflow surface in `.github/workflows/supply-chain-hardening.yml` SHALL remain the integration point until a follow-up implementation change migrates jobs to shared helpers. Existing blocking thresholds SHALL NOT be relaxed: HIGH and CRITICAL scanner findings still block, secret scanning remains mandatory, SBOM generation remains mandatory, keyless signing remains authoritative, and SLSA provenance remains required for release images.

The change SHALL NOT introduce a new production datastore, vendor-hosted control plane, cross-customer data plane, runtime graph repo-writing path, or normal-path human approval requirement. Any future implementation that writes repository files SHALL still follow the build-time OpenSpec workflow, and any runtime repo-writing path in the product SHALL remain gated by `spec_ready_for_implementation` and an existing task list.

#### Scenario: Existing guardrail is strengthened
- **WHEN** the supply-chain stabilization change is implemented
- **THEN** it reuses `.github/workflows/supply-chain-hardening.yml`, `scripts/check_license_allowlist.py`, `renovate.json`, and existing runbook locations
- **AND** no existing required scan, signing, attestation, or admission control is removed or weakened

#### Scenario: Runtime repo-writing invariant is preserved
- **WHEN** the supply-chain workflow opens pin renewal pull requests
- **THEN** that behavior is limited to repository maintenance automation
- **AND** it does not create a runtime agent path that writes customer repositories before `spec_ready_for_implementation` is true and the task list exists

### Requirement: Supply-Chain Tool Versions Are Pinned And Renewed On A Cadence

Every supply-chain tool used in CI SHALL be pinned to a version recorded in `scripts/supply_chain_versions.json`. The workflow SHALL read tool versions from that manifest rather than embedding mutable tags such as `main`, `master`, or floating major versions for supply-chain tools.

The manifest SHALL be a JSON object with:

- `schema_version`: integer manifest schema version.
- `tools`: array of tool records.

Each tool record SHALL include:

- `name`: stable tool key. Required keys are `cosign`, `syft`, `slsa-github-generator`, `hadolint`, `gitleaks`, `trufflehog`, `trivy`, `grype`, and `osv-scanner`.
- `category`: one of `signing`, `sbom`, `provenance`, `dockerfile_lint`, `secret_scan`, `vulnerability_scan`, or `license_scan`.
- `version`: exact pinned version or immutable action ref.
- `source`: upstream release or action repository.
- `datasource`: Renovate-compatible datasource where available.
- `package_name`: Renovate-compatible package name where available.
- `renewal_cadence`: `monthly` or `quarterly`.
- `last_reviewed_at`: ISO 8601 date of the last accepted renewal review.
- `force_renew_on_cve`: boolean that SHALL be `true` for all tools.

High-cadence vulnerability tools SHALL renew monthly: `trivy`, `grype`, and `osv-scanner`. All other required tools SHALL renew quarterly unless a CVE, GitHub security advisory, revoked release, or upstream deprecation requires a force-renew PR.

`renovate.json` SHALL contain a dedicated supply-chain package group for `scripts/supply_chain_versions.json`, supply-chain GitHub Actions, and supply-chain Docker or binary references. The group SHALL use the group slug `supply-chain-pins`, labels `dependencies` and `supply-chain`, and SHALL NOT automerge major, signing, provenance, or scanner upgrades. Renovate grouping SHALL be compatible with the automated opener so both mechanisms converge on the same grouped PR instead of producing competing updates.

An automated renewal opener SHALL run on a scheduled workflow and on manual dispatch. It SHALL validate the manifest schema, detect overdue pins, resolve current upstream versions using first-party release metadata where available, update only the manifest and directly related workflow references, run the supply-chain dry-run validator, and open a PR titled `chore(supply-chain): renew pinned tool versions`. Force-renew PRs triggered by a CVE or advisory SHALL be labeled `security` and `supply-chain`, SHALL be opened no later than the next business day after detection, and SHALL include the advisory identifier in the PR body.

#### Scenario: Overdue pin fires alert
- **WHEN** a tool's pinned version exceeds its renewal cadence
- **THEN** the alert fires with the tool name and the current pin age

#### Scenario: Force-renew opens a security PR
- **WHEN** a pinned tool is affected by a CVE, GitHub security advisory, revoked release, or upstream deprecation
- **THEN** the automated opener creates a renewal PR with labels `security` and `supply-chain`
- **AND** the PR body links the triggering advisory or deprecation notice
- **AND** the normal dry-run, contract validator, and fail-closed checks still apply

#### Scenario: Renovate grouping avoids competing updates
- **WHEN** Renovate detects updates to supply-chain pins or supply-chain GitHub Actions
- **THEN** it groups them under `supply-chain-pins`
- **AND** it does not automerge signing, provenance, scanner, or major-version changes
- **AND** it does not produce a second PR that conflicts with the scheduled renewal opener

### Requirement: Supply-Chain Dry-Run Runs On Every PR

A dry-run check SHALL build a tiny test image and exercise every supply-chain step against it. The dry-run image SHALL live at `backend/tests/supply_chain/dry_run/Dockerfile`. It SHALL be intentionally small, deterministic, and representative enough to exercise package discovery, operating-system package scanning, image signing, SBOM generation, provenance generation, license parsing, and vulnerability report parsing. The image SHALL use pinned base image digests and SHALL NOT depend on tenant secrets or external private registries.

The validator SHALL run from a repository script in the follow-up implementation and SHALL assert all of the following:

- SBOM file exists, is non-empty, and parses as CycloneDX JSON or SPDX JSON.
- Cosign signature verification succeeds for the dry-run image digest using the expected GitHub Actions OIDC issuer and repository identity.
- SLSA Level 3 provenance attestation exists and includes the expected repository, workflow, commit SHA, and build invocation.
- Trivy, Grype, and OSV-Scanner reports exist, are non-empty, parse as their declared formats, and retain HIGH and CRITICAL blocking thresholds.
- License allowlist output exists and `scripts/check_license_allowlist.py` reports success for the generated license reports.
- Every generated artifact is tied to the immutable dry-run image digest, not only to a mutable tag.

Each assertion SHALL include a deliberate-failure variant on a separate image or fixture under `backend/tests/supply_chain/dry_run/failures/`. Deliberate-failure variants SHALL be positive controls: the validator must detect the failure and record it as a successful detection, not as a successful supply-chain run.

#### Scenario: Missing SBOM in dry-run blocks PR
- **WHEN** the dry-run image fails SBOM generation
- **THEN** the PR check fails with a structured reason

#### Scenario: Invalid signature in dry-run blocks PR
- **WHEN** the dry-run image signature is missing or fails OIDC identity verification
- **THEN** the PR check fails with reason `signature_invalid`
- **AND** the validator includes the image digest and expected issuer in the structured output

#### Scenario: Missing scanner report in dry-run blocks PR
- **WHEN** any Trivy, Grype, or OSV-Scanner report is missing or unparsable
- **THEN** the PR check fails with reason `scanner_report_missing`
- **AND** the failed scanner name is included in the structured output

#### Scenario: Deliberate-failure variant proves the assertion can fail
- **WHEN** the deliberate-failure image is processed
- **THEN** the validator reports the expected failure
- **AND** the run is recorded as a successful detection

### Requirement: Release Workflow Is Fail-Closed On Missing Outputs

A release SHALL fail if any required supply-chain output is missing, empty, unparsable, or not bound to the image digest being released. The four required output classes are:

- SBOM: backend and frontend SBOM artifacts plus SBOM attestations attached to each image digest.
- Signature: cosign keyless signature for each release image digest.
- Provenance attestation: SLSA Level 3 provenance attestation for each release image digest.
- Scan reports: Trivy, Grype, OSV-Scanner, secret-scan, Dockerfile lint, and license allowlist reports produced for the release inputs.

Fail-closed SHALL be the default and SHALL NOT be silently disabled with `continue-on-error`, skipped artifact checks, missing `needs` edges, mutable branch refs, or a repository variable. Any temporary override SHALL require dual super-admin approval through an explicit break-glass path, SHALL be time-bound, SHALL name the release, SHALL name each missing artifact class, and SHALL write an append-only audit row before the release proceeds.

The audit row SHALL include: `event_type`, `release_id`, `image_digests`, `missing_artifacts`, `requested_by`, `approved_by`, `second_approved_by`, `rationale`, `expires_at`, `created_at`, `workflow_run_id`, and `commit_sha`. The alert `devsquad_supply_chain_fail_closed_override_total` SHALL fire whenever this override is used. Override use SHALL also be linked from the release evidence artifact.

#### Scenario: Missing attestation blocks release
- **WHEN** the release workflow finds no SLSA attestation
- **THEN** the workflow fails with reason `attestation_missing`
- **AND** no image is published to the registry

#### Scenario: Override requires dual approval
- **WHEN** an operator attempts to disable fail-closed
- **THEN** dual super-admin approval is required
- **AND** the action records an audit row and fires an alert

#### Scenario: Continue-on-error cannot hide a missing artifact
- **WHEN** a supply-chain step exits non-zero or produces no artifact
- **THEN** the release contract check fails even if the producing step used `continue-on-error`
- **AND** the release evidence artifact records the failed step and no published release is marked compliant

#### Scenario: Override use alerts operators
- **WHEN** fail-closed is bypassed through the dual super-admin override
- **THEN** `devsquad_supply_chain_fail_closed_override_total` increments with the release identifier
- **AND** the alert links the audit row and the affected workflow run

### Requirement: Each Release Produces A Linked Evidence Bundle

Every release SHALL produce a `release-evidence.json` artifact that links each image digest to its SBOM, signature, attestation, and scanner reports. The artifact SHALL be uploaded as a release asset, retained with the same retention policy as release audit evidence, and referenced from the supply-chain runbook.

`release-evidence.json` SHALL be a JSON object with:

- `schema_version`.
- `release_id`.
- `repository`.
- `commit_sha`.
- `workflow_run_id`.
- `generated_at`.
- `images`: array of image records.
- `audit`: object with override status and audit-row reference when applicable.

Each image record SHALL include:

- `name`.
- `digest`.
- `sbom_artifacts`: array of artifact paths or release asset URLs.
- `signature_ref`: cosign signature reference.
- `provenance_ref`: SLSA attestation reference.
- `scan_reports`: object containing `trivy`, `grype`, `osv_scanner`, `secret_scan`, `dockerfile_lint`, and `license_allowlist` report paths.
- `verification`: object containing validator status, timestamp, and reason when failed.

The supply-chain runbook SHALL document how to retrieve `release-evidence.json`, verify every referenced artifact, inspect override audit rows, and preserve the evidence for the configured audit retention period. Release evidence SHALL be retained for at least 365 days unless the repository retention policy requires a longer period.

#### Scenario: Auditor traces an image
- **WHEN** an auditor inspects a release tag
- **THEN** the evidence artifact lists the SBOM, signature reference, attestation reference, and scanner reports
- **AND** all referenced artifacts are reachable from the release page

#### Scenario: Release evidence records an override
- **WHEN** a release proceeds through the dual super-admin override path
- **THEN** `release-evidence.json` records the override status, audit row reference, approvers, expiry, and missing artifact classes
- **AND** the runbook instructs operators to treat the release as non-compliant until replacement evidence is attached

### Requirement: Supply-Chain Permissions Are Centralized

A composite action SHALL be introduced at `.github/actions/supply-chain-context/action.yml` in the follow-up implementation. The composite action SHALL centralize checkout, GHCR login, cosign setup, Docker Buildx setup where required, and validation of expected token scopes. Supply-chain jobs SHALL use the composite action for shared setup instead of copy-pasting login and setup steps.

GitHub Actions `permissions` blocks SHALL remain declared at workflow or job level because composite actions cannot grant permissions. The migration SHALL still centralize the required matrix in one documented contract and SHALL make jobs fail early when the caller omits required permissions. Required permissions are:

- `contents: read` for checkout and release metadata.
- `id-token: write` for keyless signing and provenance.
- `packages: write` for GHCR push and signing attachments.
- `security-events: write` only for jobs that upload SARIF.
- `actions: read` only for SLSA provenance generator jobs that require workflow metadata.

The migration path SHALL replace repeated GHCR login, cosign setup, Docker Buildx setup, and token-scope checks with the composite action first, then remove redundant per-job setup. Per-job permissions SHALL be reduced to the least-privilege set needed by that job and SHALL be reviewed by the dry-run contract.

#### Scenario: Missing permission fails early
- **WHEN** a supply-chain job calls `.github/actions/supply-chain-context` without a required permission for that job mode
- **THEN** the job fails before signing, attestation, or publishing starts
- **AND** the failure message names the missing permission and job mode

#### Scenario: Migration preserves least privilege
- **WHEN** a job is migrated to the composite action
- **THEN** it keeps only the permissions required for its supply-chain step
- **AND** the workflow no longer repeats GHCR login or signing setup outside the composite action unless a documented exception exists

### Requirement: Supply-Chain Metrics And Alerts Are Emitted

The supply-chain workflow and validators SHALL expose structured metrics and alert inputs for pin freshness, contract failures, missing evidence, dry-run health, and override use. At minimum, the following metrics SHALL be emitted or exported into the repository's observability path:

- `devsquad_supply_chain_step_failures_total{step,reason}`.
- `devsquad_supply_chain_pin_age_days{tool}`.
- `devsquad_supply_chain_pin_overdue_total{tool}`.
- `devsquad_supply_chain_evidence_missing_total{artifact}`.
- `devsquad_supply_chain_dry_run_failures_total{assertion,reason}`.
- `devsquad_supply_chain_fail_closed_override_total{release_id}`.
- `devsquad_supply_chain_release_evidence_verified_total{artifact}`.

Alerts SHALL cover overdue pins beyond cadence, dry-run failure on `main`, missing release evidence, fail-closed override use, and repeated validator failures for the same assertion. Alerts SHALL include the workflow run URL, release identifier where present, failed step, and runbook reference.

#### Scenario: Missing evidence alert includes runbook link
- **WHEN** `release-evidence.json` is absent or references an unreachable artifact
- **THEN** the evidence-missing alert fires with the release identifier, artifact class, workflow run URL, and supply-chain runbook reference

#### Scenario: Dry-run failure on main pages platform
- **WHEN** the dry-run validator fails on `main`
- **THEN** the dry-run failure alert fires with the assertion name, structured reason, and failed workflow run URL

### Requirement: Implementation Remains Deferred Until Specification Is Complete

The implementation of `scripts/supply_chain_versions.json`, the dry-run image, validator, composite action, release evidence generator, workflow migration, and automated renewal opener SHALL be deferred to a follow-up OpenSpec apply pass after this specification phase is marked complete. The follow-up implementation SHALL use this spec as the acceptance contract and SHALL include CI or script-level verification for the schema, dry-run validator, fail-closed release checks, and evidence generation.

#### Scenario: Specification phase completes without product code
- **WHEN** this OpenSpec change completes its artifact tasks
- **THEN** it may mark the specification tasks complete without creating the version manifest, dry-run image, validator, composite action, or renewal opener
- **AND** the next apply pass must implement those files before the change is eligible to archive

## Non-Goals

- Replacing GitHub Actions with another CI platform.
- Changing the signing root of trust away from cosign keyless and GitHub Actions OIDC.
- Introducing a new SBOM format beyond CycloneDX JSON or SPDX JSON.
- Weakening HIGH and CRITICAL vulnerability blocking thresholds.
- Creating any runtime agent path that writes repositories outside the protected SpecKit-style artifact gate.
