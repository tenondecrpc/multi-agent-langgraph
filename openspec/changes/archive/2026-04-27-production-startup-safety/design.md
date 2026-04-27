## Architecture Reuse

- Reuse `BACKEND_DEPLOYMENT_PROFILE` already injected into pods.
- Reuse `persistence/factory.py`, `persistence/health.py`, and the existing readiness probe contract.
- Reuse the PostgreSQL versioned-config pattern that already governs the runtime graph; the IP allowlist becomes another config entity in the same store.
- Reuse the existing audit tables (`webhook_secret_rotations`, `break_glass_grants`, `credential_rotation_schedule`, `dpa_acknowledgements`).

## Profile Matrix

| Profile      | DB required | Redis required | Vault required | Webhook gates                  | Readiness contract           |
|--------------|-------------|----------------|----------------|--------------------------------|------------------------------|
| `local`      | no          | no             | no             | minimal (signature only)       | tolerant of `not_configured` |
| `test`       | no          | no             | no             | minimal (signature only)       | tolerant of `not_configured` |
| `staging`    | yes         | yes            | yes or ESO     | full                           | strict                        |
| `production` | yes         | yes            | yes or ESO     | full                           | strict                        |
| `air_gapped` | yes         | yes            | yes or ESO     | full + vendor-egress denied    | strict + air-gapped probes    |
| `recovery`   | yes         | yes            | yes or ESO     | webhook acceptance disabled    | strict, but webhook closed    |

`recovery` exists so an operator can boot a cluster to inspect state without accepting new traffic.

Helm chart profile values are distinct from backend runtime safety profiles. `helm/values.yaml` and connected environment files use chart profile `connected`; `helm/values-staging.yaml` and `helm/values-prod.yaml` SHALL render `BACKEND_DEPLOYMENT_PROFILE=staging` and `BACKEND_DEPLOYMENT_PROFILE=production`. `helm/values-air-gapped.yaml` SHALL render `BACKEND_DEPLOYMENT_PROFILE=air_gapped`. `local`, `test`, and `recovery` are explicit runtime safety profiles and are not chart profile aliases.

## Boot Gate

At process start, the backend evaluates the profile-required configuration. Missing required values fail fast with a structured error written to logs and recorded as a `boot_failure` audit row when the database is reachable. If the database is itself missing, the failure is logged with an explicit reason and the pod stays in `CrashLoopBackOff` rather than running on `InMemory*`.

The boot-failure payload includes `event_type`, `profile`, `reason`, `missing_requirements`, `unsafe_adapter`, `secret_backend`, `db_driver`, `redis_driver`, `runbook_url`, `timestamp`, and pod metadata when available. Required reasons include `profile_unknown`, `postgresql_missing`, `redis_missing`, `secret_backend_missing`, `secret_backend_env_forbidden`, `kek_reference_missing`, `signing_key_reference_missing`, `model_catalog_missing`, `memory_adapter_forbidden`, and `air_gapped_vendor_dependency`.

Readiness is strict outside `local` and `test`: `not_configured` for database, Redis, or migration state returns 503 and a runbook reference. `local` and `test` may report warnings instead of failure.

## Webhook-Path Gates

Webhook acceptance now traverses the following gates in order, before signature verification side effects are committed:

1. Runtime profile gate (`recovery` closes webhook acceptance).
2. IP allowlist (PostgreSQL-backed).
3. HMAC signature verification with rotation overlap.
4. Tenant resolution.
5. Tenant DPA acknowledgement.
6. Tenant credential rotation status (block on overdue, unless an active break-glass grant covers the credential).
7. Idempotency and rate limit (already in place).

Each rejection writes to the existing webhook rejection audit table with a structured reason code that the operator UI can render.

Required reason codes include `recovery_profile_active`, `ip_not_allowed`, `signature_invalid`, `signature_stale`, `tenant_unknown`, `tenant_disabled`, `dpa_acknowledgement_required`, `credential_rotation_overdue`, `break_glass_grant_invalid`, `duplicate_delivery`, `rate_limited`, and `queue_unavailable`.

## IP Allowlist Migration

- A new versioned-config entity `webhook_ip_allowlist` is added.
- Cutover runs in two stages:
- Stage 1: read from PostgreSQL, fall back to environment values if PostgreSQL is empty for the tenant. Writes go to PostgreSQL only.
- Stage 2: PostgreSQL is authoritative; environment values are ignored.
- A drift alert fires if both sources disagree during stage 1.
- Rollback to environment values is allowed only during the cutover window, requires an audit row, and returns the tenant to stage 1. After the window closes, rollback uses previous PostgreSQL config versions.

## Drift Detection

- A periodic job reports `devsquad_deployment_profile_info{profile, db_driver, secret_backend}` and writes an audit row with the same fields.
- A rule alerts when `profile in {production, staging, air_gapped}` and `db_driver = "memory"` or `secret_backend = "env"` for any sample.
- The job runs every 5 minutes in non-local profiles and records rendered Helm profile, Redis driver, migration state, model catalog source, webhook acceptance mode, pod name, namespace, git SHA, and Helm release.

## Observability

- New metrics: `devsquad_boot_failures_total{reason}`, `devsquad_webhook_rejections_total{reason}` (extended), `devsquad_credential_rotation_block_webhook_total{tenant}`, `devsquad_ip_allowlist_drift_total{tenant}`.
- Alert rules reference the existing runbooks where applicable.

Additional metrics are `devsquad_readiness_failures_total{profile,reason}`, `devsquad_break_glass_webhook_acceptances_total{tenant,grant_scope}`, `devsquad_dpa_webhook_blocks_total{tenant,dpa_version}`, and `devsquad_deployment_profile_drift_total{profile,reason}`.

## Protected Workflow Invariants

- The change strengthens, never relaxes, Tier 1 controls.
- It introduces no new repo-writing surface.
- Recovery profile explicitly closes webhook acceptance to avoid accepting traffic during reconciliation.
- Both connected and `air_gapped` profiles are addressed. Missing or expired configuration blocks startup or traffic instead of silently downgrading.
