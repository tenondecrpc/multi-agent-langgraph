## Why

The constitution mandates SBOM, signing, provenance, and admission enforcement. PLAN.md requires syft SBOMs, cosign keyless signing, SLSA Level 3 provenance, Kyverno (or Sigstore policy-controller) admission, Trivy/Grype/OSV-Scanner dependency scanning that blocks on critical/high, license allowlist, pinned-digest enforcement, and Renovate with auto-merge of grouped PRs. Phase 3 set the guardrails; this change wires the full CI and admission pipeline and the cluster-side admission controller.

## What Changes

- CI build: syft-generated SBOM per image, cosign keyless signing with OIDC, SLSA Level 3 provenance, Trivy/Grype/OSV-Scanner scans blocking on critical and high.
- CI PR check: license allowlist (FOSSA or ScanCode), secret scanning (gitleaks + trufflehog), pinned-digest enforcement on base images in Dockerfiles.
- Admission: Kyverno cluster policy that rejects unsigned images and images without attached provenance; policy ships as Helm chart under `helm/` with both connected and `air_gapped` values.
- Renovate: grouped PRs, auto-merge on minor/patch when all checks pass, weekly digest for majors.
- Publish verification commands in operator docs (`cosign verify`, `cosign verify-attestation`).

## Capabilities

### New Capabilities

- `admission-control-and-attestation`: cluster-side signature and provenance verification, policy exceptions flow, emergency break-glass with audited rationale.

### Modified Capabilities

- `repository-and-supply-chain-guardrails`: wiring of SBOM, signing, provenance, scanning, and license allowlist into CI stages and Dockerfile lint.
- `release-engineering-and-feature-flags`: only signed and attested images are promotable through progressive delivery.

## Impact

- Code: `.github/workflows/` or equivalent CI definitions; `Dockerfile` lint rules; `helm/policies/` for Kyverno.
- Schema: `admission_exceptions` audit table.
- Secrets: cosign keyless uses OIDC identity; no long-lived signing key persisted.
- Deployment: Kyverno or policy-controller Helm chart under `helm/`; air-gapped profile uses locally mirrored Rekor and Fulcio or a signed-manifest-bundle approach.
- Observability: admission-denied metrics, scan-failure metrics, provenance-missing alerts.
- Tests: integration against an ephemeral K3s cluster verifying policy.
- Constitution alignment: Tier 1 preserved end-to-end.
