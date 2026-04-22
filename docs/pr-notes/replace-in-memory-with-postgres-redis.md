# PR Notes - Replace In-Memory With Postgres Redis

## High-Risk Areas

- Alembic revision `20260418_0006`
- RLS enablement on tenant-scoped persistence tables
- Vault/ESO secret wiring in Helm
- Redis-backed provider breaker and worker coordination

## Manual Verification

- Admin UI persistence panel shows migration target, applied revision, active snapshot id, and adapter readiness text.
- `GET /healthz`, `GET /readyz`, and `GET /metrics` expose the persistence health surface.
- Factory can select Postgres model catalog and Redis provider health adapters via env flags.

## Helm Dry-Run Notes

- Connected profile: `helm template dev-squad ./helm -f ./helm/values.yaml`
- Air-gapped profile: `helm template dev-squad ./helm -f ./helm/values.yaml -f ./helm/values-air-gapped.yaml`

## Rollout Notes

- Persistence rollout follows canary steps 5/25/50/100.
- Watch migration drift, DLQ depth, provider breaker state, and readiness before increasing weight.
