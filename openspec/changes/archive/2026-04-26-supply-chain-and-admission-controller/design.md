# Design: Supply Chain And Admission Controller

## Context

Phase 3 declared the guardrails but did not wire the CI pipeline or cluster-side admission policy. Without admission enforcement, unsigned images can land in the cluster, defeating the supply-chain posture.

## Goals / Non-Goals

### Goals

- Block unsigned, unscanned, unattested images at the cluster edge.
- Generate and publish SBOM and SLSA Level 3 provenance per image.
- Keep both connected and `air_gapped` profiles first-class: air-gapped deployments use mirrored Rekor and Fulcio or a verified-bundle approach, never vendor endpoints.

### Non-Goals

- No change to the runtime image content beyond lint rules.
- No runtime image introspection beyond what the admission controller performs.

## Decisions

### Decision: Cosign keyless with OIDC in CI

Images are signed using cosign keyless (Fulcio identity bound to the CI OIDC token). This avoids long-lived signing keys. Air-gapped profile documents the alternative: a local Fulcio mirror with an internal CA, or a pre-computed signed manifest bundle.

### Decision: Kyverno as the admission controller

Kyverno enforces `signature required`, `provenance required`, `SBOM attached`, `digest-pinned image reference`, `no latest tag`. Policy ships as a Helm chart in `helm/policies/`. Policy exceptions require a super_admin action recorded in `admission_exceptions` with a mandatory expiration.

### Decision: Scanning blocks on critical and high

Trivy, Grype, and OSV-Scanner run in CI and block the merge or promote on critical and high findings. Documented allowlists require rationale and expiration.

### Decision: Renovate grouping and auto-merge

Renovate groups dependency updates by ecosystem and severity. Minor and patch updates auto-merge when all checks pass. Major updates require a human review.

## Risks / Trade-offs

- CI time cost. Mitigated by layered caching and parallel jobs.
- False-positive scan findings. Mitigated by documented, expiring allowlists and weekly scan-diff review.
- Air-gapped Fulcio complexity. Mitigated by shipping verified bundles for fully offline use.

## Migration Plan

1. Add SBOM, signing, and provenance in CI without admission blocking (generate only).
2. Enable Kyverno `audit` mode in staging; collect violations.
3. Flip to `enforce` in staging; then prod.
4. Add scanning gates to CI; then to promote stages.
5. Ship Helm chart for the admission policy in both profiles.
