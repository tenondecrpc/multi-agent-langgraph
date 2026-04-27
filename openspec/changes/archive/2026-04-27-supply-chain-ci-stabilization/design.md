## Architecture Reuse

- Reuse `.github/workflows/supply-chain-hardening.yml`, `scripts/supply_chain_scan.sh`, and `scripts/check_license_allowlist.py`.
- Reuse the existing Renovate configuration (`renovate.json`) for pin renewals; group supply-chain pins into a dedicated PR group.
- Reuse the existing `helm/policies/` Kyverno chart; admission still consumes the same artifacts.

## Pinned Tool Versions

A single `scripts/supply_chain_versions.json` file SHALL list each tool, its pinned version, and the renewal cadence. The workflow SHALL read versions from this file rather than embedding them inline.

Renewal cadence: monthly for high-cadence tools (Trivy, Grype, OSV-Scanner), quarterly for the rest, with a force-renew path on CVE.

The manifest schema SHALL include `schema_version` and a `tools` array. Each tool entry records `name`, `category`, `version`, `source`, Renovate `datasource` and `package_name` where available, `renewal_cadence`, `last_reviewed_at`, and `force_renew_on_cve`. Required tool keys are `cosign`, `syft`, `slsa-github-generator`, `hadolint`, `gitleaks`, `trufflehog`, `trivy`, `grype`, and `osv-scanner`.

`renovate.json` SHALL add a dedicated `supply-chain-pins` package group with labels `dependencies` and `supply-chain`. It SHALL group manifest, supply-chain GitHub Action, and supply-chain binary or image references while keeping major, signing, provenance, and scanner updates out of automerge. The scheduled renewal opener SHALL converge on this same group so Renovate and the opener do not create competing PRs.

Force-renew triggers include CVEs, GitHub security advisories, revoked releases, and upstream deprecations. Force-renew PRs SHALL be opened no later than the next business day after detection and include the advisory identifier or deprecation reference.

## Dry-Run Check

The dry-run check builds a tiny purpose-built image (`backend/tests/supply_chain/dry_run/Dockerfile`) and runs every supply-chain step against it. The validator asserts:

1. SBOM file exists and parses as CycloneDX or SPDX.
2. Cosign signature verification succeeds with the OIDC identity.
3. SLSA Level 3 attestation exists and includes the expected build invocation.
4. Trivy, Grype, and OSV-Scanner reports exist and are parseable.
5. License allowlist check returns success.

Each assertion has a deliberate-failure variant exercised on a separate image to prove the assertion can fail.

Deliberate-failure fixtures SHALL live under `backend/tests/supply_chain/dry_run/failures/`. These fixtures are positive controls for the validator: the validator succeeds only when it detects the expected failure reason. The dry-run image SHALL pin its base image by digest and stay free of tenant secrets, private registry dependencies, and production data.

## Fail-Closed Contract

The release workflow SHALL fail if any of the four required outputs (SBOM, signature, attestation, scan reports) is missing. Today some failures are silently skipped; the new contract converts skips into hard errors.

The four required output classes are:

- SBOM: generated SBOM files plus SBOM attestations attached to release image digests.
- Signature: cosign keyless signature for every release image digest.
- Provenance attestation: SLSA Level 3 attestation for every release image digest.
- Scan reports: Trivy, Grype, OSV-Scanner, secret-scan, Dockerfile lint, and license allowlist reports.

Fail-closed cannot be bypassed with `continue-on-error`, skipped artifact checks, mutable branch refs, or repository variables. Any temporary override requires dual super-admin approval, is time-bound, names each missing artifact class, writes an append-only audit row, increments `devsquad_supply_chain_fail_closed_override_total`, and is linked from release evidence.

## Permissions And Login Matrix

A single composite action `actions/supply-chain-context` SHALL set up:

- GHCR login with the correct token scope.
- `id-token: write` for OIDC.
- `packages: write`, `contents: read`, `security-events: write`.

Every supply-chain job SHALL use the composite action; permissions SHALL NOT be repeated per job.

Because GitHub composite actions cannot grant workflow permissions, workflow and job permissions SHALL remain explicit at the caller. The composite action contract SHALL validate that the caller has the required mode-specific permissions and fail early when they are missing. Required permissions are `contents: read`, `id-token: write`, `packages: write`, `security-events: write` for SARIF upload jobs, and `actions: read` for SLSA generator jobs.

## Release Evidence Linkage

Each release SHALL produce a `release-evidence.json` artifact linking the image digest to:

- SBOM artifact path.
- Cosign signature reference.
- SLSA attestation reference.
- Trivy, Grype, OSV-Scanner report paths.
- License allowlist report path.

The artifact SHALL be uploaded as a release asset and referenced from the supply-chain runbook.

The evidence schema SHALL include `schema_version`, `release_id`, `repository`, `commit_sha`, `workflow_run_id`, `generated_at`, `images`, and `audit`. Each image record SHALL include `name`, `digest`, `sbom_artifacts`, `signature_ref`, `provenance_ref`, `scan_reports`, and `verification`. Evidence SHALL be retained for at least 365 days unless repository policy requires a longer period.

## Observability

- Metrics: `devsquad_supply_chain_step_failures_total{step}`, `devsquad_supply_chain_pin_age_days{tool}`, `devsquad_supply_chain_evidence_missing_total{artifact}`.
- Alerts: pin overdue beyond renewal cadence, evidence missing, dry-run failure on `main`.

Additional required metrics are `devsquad_supply_chain_pin_overdue_total{tool}`, `devsquad_supply_chain_dry_run_failures_total{assertion,reason}`, `devsquad_supply_chain_fail_closed_override_total{release_id}`, and `devsquad_supply_chain_release_evidence_verified_total{artifact}`. Alerts SHALL include workflow run URLs and runbook references.

## Protected Workflow Invariants

- Fail-closed cannot be disabled without dual super-admin approval and an audit row.
- The change introduces no new repo-writing surface in the runtime graph.
- Pinned versions never relax the existing scanner severity thresholds (HIGH and CRITICAL still block).

This change is Tier 1 because it reinforces mandatory supply-chain security. It does not alter the runtime ticket graph, does not add a production datastore, does not add a vendor-hosted control plane, and does not permit normal-path human approval for ticket execution. Runtime repo-writing remains gated by planner-owned artifacts, `spec_ready_for_implementation`, mandatory tests, diff guard, review approval, and pre-PR sync.

## Failure Modes

- Tool deprecation: the renewal cadence opens a PR with the new version; if the upgrade breaks a contract test, the PR is held until fixed rather than merged silently.
- OIDC identity rotation in GitHub: the composite action centralizes the configuration so a single PR fixes every job.
- Tiny dry-run image drift from real images: the dry-run image must include a representative subset of base layers.
