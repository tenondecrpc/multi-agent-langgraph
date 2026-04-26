# Helm Chart

This directory now contains the baseline chart for the persistence-backed runtime.

## Render Commands

- Connected profile:
  - `helm template dev-squad ./helm -f ./helm/values.yaml`
- Air-gapped profile:
  - `helm template dev-squad ./helm -f ./helm/values.yaml -f ./helm/values-air-gapped.yaml`

## Air-Gapped Profile

`values-air-gapped.yaml` sets `profile: air_gapped`, disables LangSmith and
external statuspage sync, rejects vendor LLM API key values at render time, and
passes `BACKEND_PROVIDER_OPENCODE_GO_ENDPOINT` to the backend. The NetworkPolicy
allows only listed internal services such as OpenCode Go and embedding pods when
`networkPolicy.denyExternalLlmEgress` is true.

Vault must be seeded before backend pods start. Use
`scripts/bootstrap_air_gapped_vault.sh` from inside the disconnected environment
and revoke the bootstrap token after the maintenance window. Vault dev mode is
not valid for this profile.

## Public Status Sync

The connected profile enables `statusPageSync.enabled` by default. The CronJob reads
`/api/v1/status-page` from the in-cluster backend service and posts the whitelist
payload to the endpoint stored in Vault at `statuspage_webhook_url`.

The air-gapped profile sets `statusPageSync.enabled: false`. In that profile,
operators use the internal admin UI public status tile or call
`/api/v1/status-page` directly from inside the customer network. No external
statuspage provider call is attempted.

## PagerDuty

`values-staging.yaml` and `values-prod.yaml` enable `pagerDuty.enabled`. The
PagerDuty routing key is pulled from Vault through External Secrets Operator
into `dev-squad-paging`; it must never be stored in Helm values or application
configuration. `values-air-gapped.yaml` disables this integration so customers
can route pages through their internal paging bridge.

## High-Risk Items

- PostgreSQL and Redis connection settings
- Vault and External Secrets Operator wiring
- NetworkPolicy egress restrictions
- Rollout strategy and readiness gates
- Connected-profile statuspage sync endpoint
- PagerDuty routing secret delivery

These are high-risk because they affect startup, secret delivery, and persistence cutover behaviour.
