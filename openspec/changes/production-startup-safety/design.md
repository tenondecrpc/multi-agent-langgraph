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

## Boot Gate

At process start, the backend evaluates the profile-required configuration. Missing required values fail fast with a structured error written to logs and recorded as a `boot_failure` audit row when the database is reachable. If the database is itself missing, the failure is logged with an explicit reason and the pod stays in `CrashLoopBackOff` rather than running on `InMemory*`.

## Webhook-Path Gates

Webhook acceptance now traverses the following gates in order, before signature verification side effects are committed:

1. IP allowlist (PostgreSQL-backed).
2. HMAC signature verification with rotation overlap.
3. Tenant DPA acknowledgement.
4. Tenant credential rotation status (block on overdue, unless an active break-glass grant covers the credential).
5. Idempotency and rate limit (already in place).

Each rejection writes to the existing webhook rejection audit table with a structured reason code that the operator UI can render.

## IP Allowlist Migration

- A new versioned-config entity `webhook_ip_allowlist` is added.
- Cutover runs in two stages:
  - Stage 1: read from PostgreSQL, fall back to environment values if PostgreSQL is empty for the tenant. Writes go to PostgreSQL only.
  - Stage 2: PostgreSQL is authoritative; environment values are ignored.
- A drift alert fires if both sources disagree during stage 1.

## Drift Detection

- A periodic job reports `devsquad_deployment_profile_info{profile, db_driver, secret_backend}` and writes an audit row with the same fields.
- A rule alerts when `profile in {production, staging, air_gapped}` and `db_driver = "memory"` or `secret_backend = "env"` for any sample.

## Observability

- New metrics: `devsquad_boot_failures_total{reason}`, `devsquad_webhook_rejections_total{reason}` (extended), `devsquad_credential_rotation_block_webhook_total{tenant}`, `devsquad_ip_allowlist_drift_total{tenant}`.
- Alert rules reference the existing runbooks where applicable.

## Protected Workflow Invariants

- The change strengthens, never relaxes, Tier 1 controls.
- It introduces no new repo-writing surface.
- Recovery profile explicitly closes webhook acceptance to avoid accepting traffic during reconciliation.
