## Why

The constitution makes both connected and `air_gapped` deployment profiles mandatory. PLAN.md specifies the profile end-to-end: bundled model catalog fallback, all fallback models pointing to self-hosted OpenCode Go, NetworkPolicy egress denial for Anthropic/OpenAI, offline telemetry posture (no LangSmith egress), offline Vault bootstrap, and a runbook. Other archived phases assumed this profile; this change validates and enforces it as a first-class product surface.

## What Changes

- Ship a consolidated `air_gapped` Helm values file with network egress denial, bundled adapters, and offline telemetry defaults.
- Default fallback model routing points to the self-hosted OpenCode Go endpoint configured via Helm values.
- Enforce NetworkPolicy denying egress to vendor LLM domains and LangSmith in the `air_gapped` profile.
- Offline Vault bootstrap script and doc; no dev-mode fallback.
- Authoritative runbook `docs/runbooks/air-gapped-deployment.md` covering install, credential seeding, drill, and recovery.
- Acceptance test profile that boots the backend with simulated vendor-unreachability and verifies correct fail-closed behavior.

## Capabilities

### New Capabilities

- `air-gapped-profile-enforcement`: Helm values, NetworkPolicy egress denial, offline telemetry posture, offline Vault bootstrap, acceptance test harness, runbook.

### Modified Capabilities

- `deployment-topology`: codifies the `air_gapped` profile as a first-class Helm profile alongside `connected`.
- `provider-routing-and-failover`: reiterates fallback model expectations for air-gapped with references to this change.

## Impact

- Code: minor config-validation improvements in provider routing; no runtime code shape changes.
- Deployment: `helm/values-air-gapped.yaml`, `NetworkPolicy` manifests, bootstrap scripts.
- Docs: `docs/runbooks/air-gapped-deployment.md` and operator guide updates.
- Tests: new acceptance-test profile and CI stage running it.
- Constitution alignment: Tier 1 preserved; air-gapped is co-equal with connected.
