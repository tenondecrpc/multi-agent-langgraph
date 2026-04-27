## Why

Several controls advertised as Tier 1 are only API-deep or rely on dev-only fallbacks that are unsafe in production:

- The persistence factory falls back to `InMemory*` adapters when no database URL is configured. `STATUS.md` calls this out explicitly: "a production deployment must provide PostgreSQL and Redis and must not rely on the fallback path." Today nothing prevents a misconfigured production deploy from booting on in-memory adapters and silently losing checkpoints, audit, and metering.
- Credential rotation blocking is described as "API-level only; not yet wired into the webhook path". An expired credential should refuse webhook acceptance, not just admin API calls.
- The webhook IP allowlist is stored in environment configuration, not the versioned PostgreSQL config store the constitution requires for tenant configuration.
- Health probes were silently flipped to ignore database and Redis state when the migration state is `not_configured` (see `persistence/health.py` fix recorded in `STATUS.md`); that is correct for local tests but must not apply when a deployment profile claims production.

This change closes those gaps by introducing a deployment profile gate enforced at boot, hardening credential and webhook control depth, and migrating the IP allowlist into PostgreSQL versioned config.

## What Changes

- Define a deployment-profile boot gate. `BACKEND_DEPLOYMENT_PROFILE in {production, staging, air_gapped}` SHALL refuse to start if any of these are missing: PostgreSQL URL, Redis URL, Vault address (or ESO equivalent), KEK reference, signing key reference, model catalog source.
- Define the readiness contract per profile: in production and air-gapped, the readiness probe SHALL fail when the database, Redis, or migration state is `not_configured`. The current "skip when not configured" behavior remains valid only in `local` and `test` profiles.
- Define webhook-path enforcement of credential rotation blocking: an overdue credential SHALL block webhook acceptance for the affected tenant, not only admin endpoints. The block reason SHALL be observable.
- Define webhook-path enforcement of break-glass grants: an active grant SHALL be honored on webhook accept and SHALL be recorded in the run's audit trail.
- Define the migration of webhook IP allowlist from environment configuration into the existing PostgreSQL versioned config tables, with audit, rollback, and shadow-mode validation reused.
- Define the per-tenant DPA gate evaluation on the webhook path so DPA acknowledgement is not bypassable by direct webhook posts.
- Define deployment-profile drift detection: a periodic check that records the active profile, the database driver, and the secret backend, and fires an alert when an unsafe combination is observed in any non-`local` profile.

## Capabilities

### Modified Capabilities

- `durable-persistence-backbone`: enforce non-negotiable production startup configuration; remove the silent in-memory fallback from non-`local` profiles.
- `webhook-and-api-protection`: extend webhook acceptance gates to cover credential rotation, break-glass, DPA, and the PostgreSQL-backed IP allowlist.
- `tenant-isolation-and-credentials`: tenant credential expiration SHALL block tenant traffic, not only admin operations.

## Tier Classification

Tier 1. The change reinforces existing non-negotiables and does not weaken any.

## Non-Goals

- Replacing the persistence adapter abstraction.
- Introducing a new secret backend.
- Cross-cluster failover for the control-plane store.
- A new audit datastore; reuse the existing audit tables.

## Operational Impact

- Production deploys that previously booted with partial configuration will now fail fast with an explicit reason. A migration period and operator runbook are required.
- IP allowlist edits move from a redeploy-driven flow to a versioned API flow; this is faster but requires backfilling current allowlists.
- Webhook-path latency increases marginally to evaluate the new gates; budget must be tracked.

## Risk

- Stricter boot gate can prevent disaster recovery boots if the operator has not staged the recovery profile correctly. The `recovery` profile must be defined to mitigate.
- Webhook-path gates introduce more rejection reasons; clients must be able to interpret them.
- Migrating the IP allowlist out of env config introduces a small window where both sources exist; precedence rules must be explicit.

## Rollback / Degradation

- The `local` and `test` profiles preserve current fallback behavior for development.
- A `recovery` profile SHALL be defined that allows booting with reduced gates for documented disaster recovery scenarios, with mandatory post-boot reconciliation.
- The IP allowlist migration SHALL run with both sources active for a configurable cutover window; environment values can be rolled back if needed.
