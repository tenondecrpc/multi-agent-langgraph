# Helm Chart

This directory now contains the baseline chart for the persistence-backed runtime.

## Render Commands

- Connected profile:
  - `helm template dev-squad ./helm -f ./helm/values.yaml`
- Air-gapped profile:
  - `helm template dev-squad ./helm -f ./helm/values.yaml -f ./helm/values-air-gapped.yaml`

## High-Risk Items

- PostgreSQL and Redis connection settings
- Vault and External Secrets Operator wiring
- NetworkPolicy egress restrictions
- Rollout strategy and readiness gates

These are high-risk because they affect startup, secret delivery, and persistence cutover behaviour.
