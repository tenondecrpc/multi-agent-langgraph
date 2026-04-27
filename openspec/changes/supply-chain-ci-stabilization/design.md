## Architecture Reuse

- Reuse `.github/workflows/supply-chain-hardening.yml`, `scripts/supply_chain_scan.sh`, and `scripts/check_license_allowlist.py`.
- Reuse the existing Renovate configuration (`renovate.json`) for pin renewals; group supply-chain pins into a dedicated PR group.
- Reuse the existing `helm/policies/` Kyverno chart; admission still consumes the same artifacts.

## Pinned Tool Versions

A single `scripts/supply_chain_versions.json` file SHALL list each tool, its pinned version, and the renewal cadence. The workflow SHALL read versions from this file rather than embedding them inline.

Renewal cadence: monthly for high-cadence tools (Trivy, Grype, OSV-Scanner), quarterly for the rest, with a force-renew path on CVE.

## Dry-Run Check

The dry-run check builds a tiny purpose-built image (`backend/tests/supply_chain/dry_run/Dockerfile`) and runs every supply-chain step against it. The validator asserts:

1. SBOM file exists and parses as CycloneDX or SPDX.
2. Cosign signature verification succeeds with the OIDC identity.
3. SLSA Level 3 attestation exists and includes the expected build invocation.
4. Trivy, Grype, and OSV-Scanner reports exist and are parseable.
5. License allowlist check returns success.

Each assertion has a deliberate-failure variant exercised on a separate image to prove the assertion can fail.

## Fail-Closed Contract

The release workflow SHALL fail if any of the four required outputs (SBOM, signature, attestation, scan reports) is missing. Today some failures are silently skipped; the new contract converts skips into hard errors.

## Permissions And Login Matrix

A single composite action `actions/supply-chain-context` SHALL set up:

- GHCR login with the correct token scope.
- `id-token: write` for OIDC.
- `packages: write`, `contents: read`, `security-events: write`.

Every supply-chain job SHALL use the composite action; permissions SHALL NOT be repeated per job.

## Release Evidence Linkage

Each release SHALL produce a `release-evidence.json` artifact linking the image digest to:

- SBOM artifact path.
- Cosign signature reference.
- SLSA attestation reference.
- Trivy, Grype, OSV-Scanner report paths.
- License allowlist report path.

The artifact SHALL be uploaded as a release asset and referenced from the supply-chain runbook.

## Observability

- Metrics: `devsquad_supply_chain_step_failures_total{step}`, `devsquad_supply_chain_pin_age_days{tool}`, `devsquad_supply_chain_evidence_missing_total{artifact}`.
- Alerts: pin overdue beyond renewal cadence, evidence missing, dry-run failure on `main`.

## Protected Workflow Invariants

- Fail-closed cannot be disabled without dual super-admin approval and an audit row.
- The change introduces no new repo-writing surface in the runtime graph.
- Pinned versions never relax the existing scanner severity thresholds (HIGH and CRITICAL still block).

## Failure Modes

- Tool deprecation: the renewal cadence opens a PR with the new version; if the upgrade breaks a contract test, the PR is held until fixed rather than merged silently.
- OIDC identity rotation in GitHub: the composite action centralizes the configuration so a single PR fixes every job.
- Tiny dry-run image drift from real images: the dry-run image must include a representative subset of base layers.
