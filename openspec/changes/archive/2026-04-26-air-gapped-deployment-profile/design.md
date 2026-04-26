# Design: Air-Gapped Deployment Profile

## Context

Multiple archived changes and the active persistence change reference the air-gapped profile. What is missing is the consolidated values, NetworkPolicy enforcement, an end-to-end acceptance test, and a canonical runbook.

## Goals / Non-Goals

### Goals

- One Helm values file captures the profile.
- NetworkPolicy denies egress to vendor LLM and telemetry domains.
- Default LLM routing falls back to self-hosted OpenCode Go.
- Offline Vault bootstrap works without dev-mode.
- Acceptance test enforces the profile in CI.

### Non-Goals

- No custom LLM serving infrastructure beyond wiring OpenCode Go.
- No changes to observability semantics beyond disabling external exporters.

## Decisions

### Decision: Profile declared via Helm values

`values-air-gapped.yaml` sets `air_gapped: true` and propagates to env vars consumed by persistence health, provider routing, telemetry, and admission. Config validation rejects connected-only options (vendor LLM keys) when `air_gapped` is true.

### Decision: NetworkPolicy egress denial

A `NetworkPolicy` denies egress to vendor LLM provider CIDRs and telemetry domains. The cluster provides an internal DNS entry for the OpenCode Go endpoint.

### Decision: Offline Vault bootstrap

A bootstrap script unseals Vault using operator-held unseal keys and configures auth methods and policies without network access. Documentation emphasizes no dev-mode and no root token reuse.

### Decision: Acceptance test profile in CI

A dedicated CI job spins up the stack with the `air_gapped` Helm profile and simulates vendor-unreachability. It runs a smoke ticket through the pipeline, expecting fail-closed behavior on any accidental external call.

## Risks / Trade-offs

- Missed NetworkPolicy rules. Mitigated by egress-blackhole default-deny baseline plus explicit allow for internal services.
- OpenCode Go availability. Mitigated by health checks and a documented fallback plan.

## Migration Plan

1. Ship `values-air-gapped.yaml` and NetworkPolicy manifests.
2. Wire config validation rejecting connected-only options.
3. Add the acceptance-test CI stage in warn-only mode.
4. Flip to enforce.
5. Publish runbook.
