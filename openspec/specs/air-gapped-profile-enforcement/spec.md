# air-gapped-profile-enforcement Specification

## Purpose

Consolidated air-gapped deployment profile enforcement. Created by archiving change 2026-04-26-air-gapped-deployment-profile.

## Requirements

### Requirement: Consolidated Air-Gapped Helm Profile

The repository SHALL ship `helm/values-air-gapped.yaml` that sets `air_gapped: true`, selects internal LLM fallback routing, disables external telemetry exporters, and applies NetworkPolicy egress denial. Config validation SHALL reject connected-only options when the profile is active.

#### Scenario: Connected-only option is rejected
- **WHEN** the profile is air-gapped and a Helm value sets a vendor LLM API key
- **THEN** boot fails with a structured configuration error

### Requirement: NetworkPolicy Denies Egress To Vendor Endpoints

A `NetworkPolicy` in the air-gapped profile SHALL deny egress to vendor LLM and telemetry domains and allow only internal services. Any accidental external call SHALL be refused at the network layer.

#### Scenario: Accidental egress to vendor endpoint is refused
- **WHEN** a pod attempts to reach a vendor LLM endpoint
- **THEN** the connection is refused
- **AND** the attempt is observable via NetworkPolicy metrics

### Requirement: Default Fallback Routing To Self-Hosted OpenCode Go

In the air-gapped profile, default LLM routing SHALL fall back to a self-hosted OpenCode Go endpoint configured via Helm values.

#### Scenario: Ticket runs without vendor LLMs
- **WHEN** a ticket is accepted in air-gapped mode
- **THEN** the routing layer selects the OpenCode Go endpoint for its default path
- **AND** provider-health signals reflect only internal endpoints

### Requirement: Offline Vault Bootstrap Without Dev-Mode

Vault SHALL boot in the air-gapped profile using operator-held unseal keys and predefined auth methods. Dev-mode SHALL NOT be used.

#### Scenario: Vault boots offline
- **WHEN** Vault starts in air-gapped mode
- **THEN** it unseals using operator-held keys
- **AND** no dev-mode flags are present

### Requirement: Acceptance Test Enforces The Profile In CI

A CI job SHALL deploy the stack with the air-gapped Helm profile, simulate vendor-unreachability, run a smoke ticket through the pipeline, and verify fail-closed behavior on any attempted external call.

#### Scenario: Accidental external call fails the CI job
- **WHEN** the smoke ticket attempts a vendor endpoint call
- **THEN** the CI job fails with the offending call captured
- **AND** the PR cannot merge
