# durable-persistence-backbone Specification

## Purpose
Defines the requirements for the single persistence module that owns all stateful adapters - connection factories, session management, Redis client factories, envelope-encryption helpers, migration runners, and concrete adapters for every repository, ledger, registry, queue client, and guard used by the rest of the backend. Added by change replace-in-memory-with-postgres-redis.

## Requirements

### Requirement: Single Persistence Module Owns All Stateful Adapters

The backend SHALL expose a single `persistence` module that owns connection factories, session management, Redis client factories, envelope-encryption helpers, migration runners, and concrete adapters for every repository, ledger, registry, queue client, and guard used by the rest of the backend. Every other module MUST depend on persistence contracts (Protocols) and MUST NOT construct `InMemory*` adapters or raw database or Redis clients directly in production code paths.

#### Scenario: Production code depends on contracts, not adapters
- **WHEN** any non-persistence module needs a run repository, control-plane store, handler registry, worker controller, queue client, budget ledger, metering ledger, model catalog, provider health store, or webhook guard
- **THEN** it obtains the implementation from the persistence DI factory
- **AND** it imports only the Protocol from `persistence.contracts`
- **AND** no production wiring path resolves any `InMemory*` adapter

#### Scenario: In-memory adapters remain available only as test doubles
- **WHEN** tests configure the persistence factory
- **THEN** the factory may select `InMemory*` adapters moved under `persistence.testing`
- **AND** those adapters are never returned by the production factory

### Requirement: PostgreSQL Is The System Of Record

The backend SHALL persist every piece of state that must survive process restart, be audited, be backed up, or feed reporting in PostgreSQL 16 HA. No other datastore MAY own that role. Optional internal knowledge retrieval MUST reuse PostgreSQL via `pgvector`.

#### Scenario: State that must be auditable or recoverable lands in PostgreSQL
- **WHEN** the backend writes ticket runs, control-plane versions and snapshots, audit events, budget reservations and charges, metering facts, DLQ records, webhook idempotency records, model-catalog entries, or shadow reports
- **THEN** the authoritative record is a row in a PostgreSQL table managed by this module
- **AND** no authoritative copy lives only in Redis, in local files, or in process memory

#### Scenario: No new production datastore is introduced
- **WHEN** a design proposes a new persistence target for any of the above
- **THEN** the proposal is rejected unless it is PostgreSQL (with optional `pgvector`) or Redis already declared in the constitution

### Requirement: Redis Is Scoped To Coordination, Transport, And Short-Lived Caches

The backend SHALL use Redis 7 only for queue transport (ARQ), pub/sub (snapshot invalidation), coordination primitives (drain leases, in-flight counters, race-free budget reservation counters under PostgreSQL write-through), the shared circuit breaker, and bounded-TTL caches for webhook dedupe and read-through lookups.

#### Scenario: Redis is never the authoritative record
- **WHEN** a Redis key expires, is evicted, or is lost during cluster failover
- **THEN** the subsystem reconstructs the live state from PostgreSQL without data loss for any auditable record

#### Scenario: Redis outage triggers fail-closed behavior on risk-sensitive paths
- **WHEN** Redis is unreachable and the operation guards a budget reservation, a circuit-breaker check, or a rate limit
- **THEN** the operation fails closed and raises a typed persistence error
- **AND** the event is logged as a persistence incident with tenant and team context

### Requirement: Tenant And Team Scoping Is An Interface Invariant

Every repository, ledger, store, registry, queue client, and guard method that touches tenant data SHALL require a tenant context (tenant_id, team_id, optional project_id), parameterise every query with it, and set a per-transaction PostgreSQL GUC so row-level security policies enforce isolation at the database layer.

#### Scenario: Missing tenant context is a programming error
- **WHEN** a caller invokes a tenant-scoped method without a tenant context
- **THEN** the method raises immediately before issuing any query
- **AND** the error is observable and never silently downgrades to a cross-tenant query

#### Scenario: Row-level security blocks cross-tenant reads
- **WHEN** a session attempts to read rows for a tenant other than the one set on the session GUC
- **THEN** PostgreSQL row-level security blocks the read
- **AND** the application surfaces a typed authorization error

### Requirement: Application-Layer Envelope Encryption For Sensitive Columns

The backend SHALL encrypt credentials, OAuth tokens, LLM API keys, and any customer-supplied secrets at the application layer using envelope encryption with a data-encryption key wrapped by a KMS or Vault master key reference. Ciphertext, plaintext, and key material MUST never be written to logs or metrics.

#### Scenario: Sensitive columns are encrypted on write
- **WHEN** the persistence layer stores a sensitive field
- **THEN** it writes `<column>_ciphertext`, `<column>_dek_id`, and `<column>_nonce`
- **AND** no plaintext column exists for that field in the schema

#### Scenario: Key rotation supports dual-read
- **WHEN** a key-rotation job is in progress
- **THEN** the adapter can decrypt rows wrapped by the old key and re-encrypt with the new key
- **AND** the rotation completes without downtime or credential loss

### Requirement: Expand/Contract Migrations With Reversibility Tests

Every schema change SHALL follow expand/contract discipline. Each Alembic migration MUST have a reversibility test that runs `alembic upgrade head` and `alembic downgrade -1` against an ephemeral database with seeded rows and asserts lossless round-trip for non-destructive steps.

#### Scenario: A destructive migration ships as expand then contract
- **WHEN** a migration drops a column or table
- **THEN** the drop lands in a contract migration that runs only after the expand migration is deployed and backfill completes
- **AND** the expand migration is independently deployable with both old and new code paths

#### Scenario: Reversibility tests gate merges
- **WHEN** CI runs
- **THEN** the migration test suite applies each migration, rolls it back, and reapplies it
- **AND** a failure blocks the merge

### Requirement: Connection Pooling, Timeouts, And Graceful Shutdown

The persistence module SHALL own asyncpg and Redis connection pools with bounded sizes configured via Helm values, enforce per-query statement timeouts, and flush active work to checkpoint boundaries before closing pools on shutdown.

#### Scenario: Readiness flips on drain start
- **WHEN** the process receives SIGTERM
- **THEN** the readiness probe begins failing immediately
- **AND** active sessions continue until they reach a LangGraph checkpoint boundary or ARQ job completion
- **AND** pools close only after drain completes

#### Scenario: Pool saturation is observable
- **WHEN** the pool is above its configured high-water mark
- **THEN** the persistence module emits a `pool_saturation` metric above threshold
- **AND** an alert fires via the standard alerting pipeline

### Requirement: Persistence Health Surface

The backend SHALL expose dedicated liveness and readiness signals for persistence covering database reachability, Redis reachability, migration version, active snapshot presence, and pool health.

#### Scenario: Migration drift blocks readiness
- **WHEN** the deployed code expects a migration version newer than what is applied
- **THEN** readiness fails with a structured reason
- **AND** the liveness probe remains green so the pod can self-apply a pending migration if configured

#### Scenario: Redis unreachable fails only readiness when fallback is safe
- **WHEN** Redis is unreachable
- **THEN** readiness fails if any required coordination primitive is unavailable
- **AND** liveness remains green unless the process state is actually corrupted

### Requirement: Air-Gapped Deployment Is A First-Class Profile

The persistence module SHALL operate correctly in an `air_gapped` deployment profile. All adapters MUST provide fail-closed behavior when optional outbound services are unreachable and MUST NOT require any vendor-hosted service.

#### Scenario: Air-gapped profile uses bundled fallbacks
- **WHEN** the deployment runs with `air_gapped: true`
- **THEN** the model catalog adapter reconciles against the bundled YAML as the fallback source of truth
- **AND** the provider-health adapter applies the fail-closed policy declared in config when Redis is unreachable

#### Scenario: No vendor-hosted dependency is required
- **WHEN** the persistence module boots in air-gapped mode
- **THEN** all required services resolve inside the customer-owned cluster
- **AND** no outbound network call is attempted against vendor-operated endpoints

### Requirement: Deployment Profile Names Are Unambiguous

The backend SHALL distinguish Helm deployment profile values from backend runtime safety profiles. Helm values MAY use `profile: connected` or `profile: air_gapped` to select chart behavior, while `BACKEND_DEPLOYMENT_PROFILE` SHALL use one of `local`, `test`, `staging`, `production`, `air_gapped`, or `recovery` to select backend startup safety behavior. `helm/values-staging.yaml` and `helm/values-prod.yaml` SHALL map the connected chart profile to backend runtime profiles `staging` and `production` respectively. `helm/values-air-gapped.yaml` SHALL map to backend runtime profile `air_gapped`.

The backend SHALL reject unknown profile names at boot with reason `profile_unknown`. A connected chart profile SHALL NOT be treated as a backend runtime safety profile.

#### Scenario: Connected Helm production maps to production runtime profile
- **WHEN** the production Helm values render backend environment variables
- **THEN** `BACKEND_DEPLOYMENT_PROFILE` is `production`
- **AND** the backend applies the non-local boot gate and strict readiness contract

#### Scenario: Unknown runtime profile fails boot
- **WHEN** `BACKEND_DEPLOYMENT_PROFILE` is not one of the supported runtime profile values
- **THEN** startup fails with reason `profile_unknown`
- **AND** no in-memory fallback is selected

### Requirement: Non-Local Profiles Refuse To Start On In-Memory Adapters

When `BACKEND_DEPLOYMENT_PROFILE` is `staging`, `production`, `air_gapped`, or `recovery`, the backend SHALL refuse to start unless PostgreSQL, Redis, the configured secret backend, and the model catalog source are reachable. In-memory fallbacks SHALL be available only in `local` and `test` profiles.

The boot gate SHALL enforce the following profile matrix:

| Runtime profile | PostgreSQL URL | Redis URL | Secret backend | KEK reference | Signing key reference | Model catalog source | Webhook acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `local` | optional | optional | optional | optional | optional | optional bundled or memory | open after minimal signature gate |
| `test` | optional | optional | optional | optional | optional | optional fixtures | open for test harness only |
| `staging` | required and reachable | required and reachable | Vault or ESO required | required | required | PostgreSQL or reviewed bundled seed | open after full gates |
| `production` | required and reachable | required and reachable | Vault or ESO required | required | required | PostgreSQL authoritative source | open after full gates |
| `air_gapped` | required and reachable | required and reachable | internal Vault or ESO required | required | internal signing root required | bundled seed plus PostgreSQL reconciliation | open after full gates and vendor-egress denial |
| `recovery` | required and reachable | required and reachable | Vault or ESO required | required | required | PostgreSQL or reviewed bundled seed | closed with `recovery_profile_active` |

Boot failures SHALL be logged as structured JSON with `event_type=boot_failure`, `profile`, `reason`, `missing_requirements`, `unsafe_adapter`, `secret_backend`, `db_driver`, `redis_driver`, `runbook_url`, `timestamp`, and `pod_name` when available. If PostgreSQL is reachable, the backend SHALL also write an audit row with those fields plus `git_sha` and `helm_release`. If PostgreSQL is not reachable, the structured log is authoritative and the process exits before accepting traffic.

Required boot failure reason codes are `profile_unknown`, `postgresql_missing`, `postgresql_unreachable`, `redis_missing`, `redis_unreachable`, `secret_backend_missing`, `secret_backend_env_forbidden`, `kek_reference_missing`, `signing_key_reference_missing`, `model_catalog_missing`, `memory_adapter_forbidden`, and `air_gapped_vendor_dependency`.

#### Scenario: Production boot without database fails fast
- **WHEN** the pod starts in `production` without a database URL
- **THEN** startup fails with a structured boot-failure log
- **AND** the pod does not enter `Ready` state

#### Scenario: Local boot still allows in-memory adapters
- **WHEN** the pod starts in `local` without a database URL
- **THEN** startup succeeds using in-memory adapters
- **AND** readiness reports `local` profile

### Requirement: Readiness Probe Is Strict Outside Local And Test

In `staging`, `production`, `air_gapped`, and `recovery` profiles, the readiness probe SHALL report `not_ready` when the database, Redis, or migration state is `not_configured`. The current tolerance only applies to `local` and `test`.

For non-`local` and non-`test` profiles, `/readyz` SHALL return HTTP 503 when any required dependency is missing, unreachable, unhealthy, or reports migration state `not_configured`. The readiness payload SHALL include `status`, `profile`, `reasons`, `dependencies`, `migration_state`, `runbook_url`, and `recovery_allowed`. The `runbook_url` SHALL point to the production startup safety runbook or the closest existing persistence runbook until that runbook is implemented. `local` and `test` MAY return HTTP 200 with warnings when dependencies are not configured.

#### Scenario: Production readiness fails on missing migration state
- **WHEN** the pod runs in `production` and the migration state reports `not_configured`
- **THEN** `/readyz` returns `503` with reason `database_unhealthy` or `migration_drift`
- **AND** the response includes the runbook URL

#### Scenario: Local readiness reports warning
- **WHEN** the pod runs in `local` and PostgreSQL is not configured
- **THEN** `/readyz` may return `200`
- **AND** the payload includes profile `local` and warning `not_configured_tolerated`

### Requirement: Recovery Profile Closes Webhook Acceptance

The `recovery` profile SHALL boot with the same persistence and secret guarantees as `production`, but SHALL refuse to accept any webhook traffic. It exists only for disaster recovery inspection, repair, migration reconciliation, and administrative read or repair operations. It SHALL NOT enqueue new ticket runs, accept Jira or GitHub webhooks, mint new integration tokens for normal work, or run worker dispatch for new tenant traffic.

#### Scenario: Recovery boot rejects webhook
- **WHEN** the pod runs in `recovery` profile and a webhook arrives
- **THEN** the pod returns a structured rejection with reason `recovery_profile_active`
- **AND** the readiness probe stays `ok` for management endpoints

#### Scenario: Recovery cannot enqueue new work
- **WHEN** an operator attempts to enqueue a new ticket run while `recovery` is active
- **THEN** the request is rejected with reason `recovery_profile_active`
- **AND** the audit trail records that recovery mode blocked tenant traffic

### Requirement: Profile Drift Detection Records Runtime Safety State

A periodic drift detection job SHALL record the active runtime profile, rendered Helm profile, database driver, Redis driver, secret backend, migration state, model catalog source, and whether webhook acceptance is open. The job SHALL run at least every 5 minutes in `staging`, `production`, `air_gapped`, and `recovery`, and at least hourly in `local` or `test` when enabled.

The audit row SHALL include `event_type=deployment_profile_drift_check`, `profile`, `helm_profile`, `db_driver`, `redis_driver`, `secret_backend`, `migration_state`, `model_catalog_source`, `webhook_acceptance`, `safe`, `reasons`, `observed_at`, `pod_name`, `namespace`, `git_sha`, and `helm_release`.

#### Scenario: Non-local memory adapter alerts
- **WHEN** the drift job observes `profile=production` and `db_driver=memory`
- **THEN** `devsquad_deployment_profile_drift_total{reason="memory_adapter_forbidden"}` increments
- **AND** a critical alert references the startup safety runbook
