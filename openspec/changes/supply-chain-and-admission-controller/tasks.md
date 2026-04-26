## 1. Artifact Alignment

- [ ] 1.1 Confirm scope does not duplicate Phase 3 guardrail spec; extend rather than rewrite.

## 2. CI Build Hardening

- [x] 2.1 Add syft SBOM generation and publish as artifact.
- [ ] 2.2 Add cosign keyless signing bound to the CI OIDC identity.
- [ ] 2.3 Add SLSA Level 3 provenance generation and attach to image.
- [x] 2.4 Add Trivy, Grype, OSV-Scanner; block on critical and high.

## 3. PR Checks

- [ ] 3.1 License allowlist enforcement via FOSSA or ScanCode.
- [x] 3.2 Secret scanning via gitleaks and trufflehog.
- [x] 3.3 Dockerfile lint: digest-pinned base images, no `latest` tag.

## 4. Admission Controller

- [ ] 4.1 Author Kyverno policies: signature required, provenance required, digest-pinned, no-latest.
- [ ] 4.2 Ship Helm chart under `helm/policies/` with connected and `air_gapped` values.
- [ ] 4.3 Add `admission_exceptions` table and API; exceptions require super_admin and have mandatory `expires_at`.
- [ ] 4.4 Audit mode in staging first; then enforce; then prod.

## 5. Renovate

- [ ] 5.1 Config for grouped PRs and auto-merge on minor/patch with all checks green.
- [ ] 5.2 Major updates require human review.

## 6. Observability

- [ ] 6.1 Metrics: admission-denied count per policy, scan-failure count, SBOM/provenance missing count.
- [ ] 6.2 Runbooks: signature failure, provenance failure, exception approval.

## 7. Verification

- [ ] 7.1 Ephemeral K3s integration test validates policy in enforce mode.
- [ ] 7.2 Air-gapped bundle verification via offline test harness.

## 8. Archive

- [ ] 8.1 Archive after enforce mode stable in production.
