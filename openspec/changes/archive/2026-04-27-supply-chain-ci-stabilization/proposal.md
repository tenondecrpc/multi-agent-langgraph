## Why

The most recent ten or so commits on `main` are repeated fixes to the supply-chain workflow: `cosign attach sbom` flag drift, GHCR login, missing permissions on the SLSA generator job, OSV-Scanner reference, and `cryptography` pin. The pipeline is comprehensive on paper but fragile in practice. Every brittle CI failure on `main` is a Tier 1 supply-chain regression and erodes confidence that signing, provenance, and SBOM attachment actually run on every release.

This change defines the stabilization contract: pinned tool versions, contract tests for each step, dry-run validation in PRs, and a ratchet that prevents regressions from passing silently.

## What Changes

- Define pinned versions for each supply-chain tool (cosign, syft, slsa-github-generator, hadolint, gitleaks, trufflehog, Trivy, Grype, OSV-Scanner) with renewal cadence.
- Define a "supply-chain dry-run" PR check that exercises every step against a tiny image so the workflow itself is tested before reaching `main`.
- Define a contract test per step: each step SHALL emit a parseable artifact (SBOM, signature, attestation, scan report) that the dry-run validator inspects.
- Define the GHCR login matrix and required permissions per job, codified once and referenced rather than copy-pasted.
- Define a ratchet: SBOM attachment, signature, and provenance are required outputs; the workflow SHALL fail closed if any output is missing.
- Define a renewal cadence for pinned versions with an automated PR opener.
- Define an evidence link from each release to the four artifacts (SBOM, signature, provenance attestation, scan reports) so auditors can trace any image to its provenance.

## Capabilities

### Modified Capabilities

- `repository-and-supply-chain-guardrails`: pin tool versions, add CI dry-run, add contract tests per step, add release-time evidence linkage.

## Tier Classification

Tier 1. The change reinforces existing supply-chain non-negotiables.

## Non-Goals

- Replacing GitHub Actions with another CI platform.
- A new signing root of trust; cosign keyless and the existing OIDC identity remain authoritative.
- A new SBOM format; CycloneDX or SPDX as already produced by syft remain authoritative.

## Operational Impact

- Pin renewals require small PRs; the automated opener mitigates the burden.
- The dry-run check adds CI minutes per PR. Budget impact is bounded by using a tiny test image.
- The fail-closed contract converts brittle silent failures into explicit blockers; some PRs that previously merged with broken supply-chain steps will now block.

## Risk

- Aggressive pinning can lag behind security patches; the renewal cadence must be enforced.
- The dry-run image must remain small enough that the check stays fast.
- A misconfigured contract test can produce false negatives that block legitimate releases; each contract test must include a positive control.

## Rollback / Degradation

- Pin renewals roll forward through PRs; reverting a pin is a normal git revert.
- The dry-run check can be temporarily disabled via a labeled override that requires super-admin approval and writes an audit row.
- Fail-closed cannot be disabled; an outage of the supply-chain pipeline halts releases by design.
