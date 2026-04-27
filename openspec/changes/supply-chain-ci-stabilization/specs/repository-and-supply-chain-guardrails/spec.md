## ADDED Requirements

### Requirement: Supply-Chain Tool Versions Are Pinned And Renewed On A Cadence

Every supply-chain tool used in CI SHALL be pinned to a version recorded in `scripts/supply_chain_versions.json`. The renewal cadence SHALL be enforced with an automated PR opener and a metric that surfaces overdue pins.

#### Scenario: Overdue pin fires alert
- **WHEN** a tool's pinned version exceeds its renewal cadence
- **THEN** the alert fires with the tool name and the current pin age

### Requirement: Supply-Chain Dry-Run Runs On Every PR

A dry-run check SHALL build a tiny test image and exercise every supply-chain step against it. The validator SHALL assert SBOM presence, signature validity, attestation presence, scanner reports, and license allowlist outcome. Each assertion SHALL include a deliberate-failure variant on a separate image.

#### Scenario: Missing SBOM in dry-run blocks PR
- **WHEN** the dry-run image fails SBOM generation
- **THEN** the PR check fails with a structured reason

#### Scenario: Deliberate-failure variant proves the assertion can fail
- **WHEN** the deliberate-failure image is processed
- **THEN** the validator reports the expected failure
- **AND** the run is recorded as a successful detection

### Requirement: Release Workflow Is Fail-Closed On Missing Outputs

A release SHALL fail if any of SBOM, cosign signature, SLSA attestation, or scanner reports is missing. The fail-closed behavior SHALL be disablable only via dual super-admin approval that writes an audit row and fires an alert.

#### Scenario: Missing attestation blocks release
- **WHEN** the release workflow finds no SLSA attestation
- **THEN** the workflow fails with reason `attestation_missing`
- **AND** no image is published to the registry

#### Scenario: Override requires dual approval
- **WHEN** an operator attempts to disable fail-closed
- **THEN** dual super-admin approval is required
- **AND** the action records an audit row and fires an alert

### Requirement: Each Release Produces A Linked Evidence Bundle

Every release SHALL produce a `release-evidence.json` artifact that links the image digest to its SBOM, signature, attestation, and scanner reports. The artifact SHALL be referenced from the supply-chain runbook.

#### Scenario: Auditor traces an image
- **WHEN** an auditor inspects a release tag
- **THEN** the evidence artifact lists the SBOM, signature reference, attestation reference, and scanner reports
- **AND** all referenced artifacts are reachable from the release page
