# Design: Replace In-Memory Storage With Real Persistence

## Context

The current backend under `backend/src/backend/` implements every stateful subsystem as `InMemory*` classes:

- `runtime/store.py` - `InMemoryRunRepository`
- `control_plane/store.py` - `InMemoryControlPlaneStore`
- `control_plane/graph.py` - `InMemoryHandlerRegistry`
- `platform/queue.py` - `InMemoryWorkerController`, `WeightedFairDispatcher` (pure function)
- `governance/budget.py` - `InMemoryBudgetLedger`
- `governance/metering.py` - `InMemoryMeteringLedger`
- `governance/catalog.py` - `InMemoryModelCatalog`
- `governance/routing.py` - `InMemoryProviderHealthStore`
- `security/webhook.py` - `InMemoryWebhookGuard`

These satisfy unit tests but cannot survive pod restarts, cannot be shared across replicas, cannot be audited, and cannot meet Tier 1 non-negotiables (parallel workers, race-free budgets, Redis-shared circuit breaker, DLQ, graceful shutdown to checkpoint boundary, DR with RPO and RTO, config versioning with rollback and audit).

The constitution (`openspec/config.yaml`) and `AGENTS.md` already fix the durable stack:

- PostgreSQL 16 HA for checkpoints, memory, config, audit, metering, plus optional `pgvector`.
- Redis 7 Cluster for queueing, pub/sub, idempotency, circuit breaker, short-window caches.
- ARQ on Redis for the worker queue.
- LangGraph `langgraph-checkpoint-postgres` and `langgraph.store.postgres` for graph checkpoints and long-term memory.
- HashiCorp Vault plus External Secrets Operator for secrets; envelope encryption at the application layer for sensitive fields.
- Both connected and `air_gapped` deployment profiles are mandatory.

No new production datastore may be introduced.

## Goals / Non-Goals

### Goals

- Give every stateful subsystem a durable backing store that matches Tier 1 requirements.
- Preserve existing public interfaces where reasonable so callers do not rewrite business logic; only the implementation swaps.
- Keep tests fast via an `InMemory*` adapter kept as a test double behind a common interface.
- Support connected and `air_gapped` deployments from day one.
- Introduce expand/contract migration discipline with reversibility tests.
- Expose health, migration status, pool saturation, Redis command latency, and DLQ depth as first-class observability.

### Non-Goals

- No new datastore families (no Kafka, no MongoDB, no DynamoDB, no standalone vector DB). Optional RAG stays on `pgvector` only and remains disabled at GA.
- No change to the ticket pipeline graph shape, the artifact chain, the repo-write gate, the diff-size guard, the forbidden-path guard, the review gate, or the pre-PR sync.
- No change to OIDC, RBAC, webhook HMAC freshness, sandboxing, or supply-chain security scope beyond additive observability.
- No vendor-hosted control plane and no cross-customer data plane. Nothing in this design is SaaS.

## Decisions

### Decision: Single persistence module with explicit adapter boundaries

Introduce `backend/src/backend/persistence/` that owns the connection factory, session management, Redis client factory, envelope-encryption helper, migration runner, health surface, and the concrete adapters for each subsystem. Every other module depends on the interface, not the adapter.

What changes:

- A DI factory exposes `RunRepository`, `ControlPlaneStore`, `HandlerRegistry`, `WorkerController`, `QueueClient`, `BudgetLedger`, `MeteringLedger`, `ModelCatalog`, `ProviderHealthStore`, `WebhookGuard`.
- Production wiring selects the Postgres-plus-Redis adapters; tests select the in-memory adapters.
- Each interface becomes a typed Protocol in `persistence/contracts.py`; the existing `InMemory*` classes are moved under `persistence/testing/` and are test-only.

Alternatives considered:

- Let each module own its own adapter. Rejected: duplicates pool configuration, migration plumbing, observability, encryption.
- Use a thick ORM layer everywhere. Rejected: `SQLAlchemy 2.x async` is the right level of abstraction for CRUD and joins, but checkpoint and queue paths stay on dialect-specific primitives (LangGraph `PostgresSaver`, ARQ on Redis) to keep performance and semantics correct.

### Decision: PostgreSQL as the system of record; Redis for coordination and short-lived state

PostgreSQL owns anything that must survive restart, be audited, be backed up, be reported on, or be rolled back. Redis owns anything that is transport (ARQ queues, pub/sub), coordination (drain leases, in-flight counters, circuit breaker), or cache (short-window webhook dedupe, handler-registry invalidation).

What this means per subsystem:

- Runs and checkpoints: `runs` table plus LangGraph `PostgresSaver` tables. Pause and resume transitions are atomic with state updates via `SELECT ... FOR UPDATE` or advisory locks.
- Control-plane config: `graph_versions`, `agent_versions`, `snapshots`, `run_snapshot_bindings`, `shadow_reports`, `audit_events`. Activations and rollbacks are transactional. `audit_events` is append-only and indexed by `(target_id, created_at)`.
- Handler registry: process-local cache keyed by `snapshot_id`, invalidated by Redis pub/sub channel `control_plane:snapshot_activated`. Any miss reloads from PostgreSQL.
- Worker queue: ARQ on Redis for transport; `dead_letter_records` table in PostgreSQL for durable DLQ with retention; Redis sorted sets for in-flight counters; Redis strings with TTL for drain leases; weighted-fair selection stays a pure function but is fed by Redis counters.
- Budget ledger: durable rows in `budget_reservations` and `budget_charges`; Redis holds live atomic counters keyed by `(tenant_id, team_id, ticket_id)` to guarantee race-free decrement under concurrent workers using a Lua script; every reservation and commit writes through to PostgreSQL in the same unit of work before Redis is decremented.
- Metering: `metering_facts` table partitioned by `created_at` month; hourly rollups via a scheduled ARQ job; CSV export remains the Tier 2 degradation path.
- Model catalog: `model_catalog` table is the source of record; a bundled YAML remains shipped with the container image as the air-gapped fallback and is reconciled at boot.
- Provider health and circuit breaker: Redis hash keyed by `(provider, region)` with a TTL; writes behind a Lua script; if Redis is unreachable in air-gapped mode, the adapter falls back to a local-circuit-breaker fail-closed policy declared in config, never silently permits unbounded calls.
- Webhook idempotency: `webhook_idempotency_records` table keyed by `(source, delivery_id)` with a unique constraint; Redis holds a short-window dedupe set with TTL equal to the freshness window to absorb bursts without hitting PostgreSQL.

### Decision: Expand/contract migrations with reversibility tests

Alembic is the migration tool. Every migration ships in two parts when schema changes are destructive: an expand migration that adds new columns or tables without breaking the old code, and a contract migration that drops unused structure only after the rolling deploy completes. Each migration has an accompanying test that runs `alembic upgrade head` and `alembic downgrade -1` against an ephemeral database and asserts that round-trips are lossless for seeded rows.

High-risk flag: DB migrations are called out in the Tasks file and in PR descriptions, consistent with the constitution's high-risk list.

### Decision: Application-layer envelope encryption

Sensitive columns (Jira and GitHub credentials, LLM API keys, any OAuth refresh tokens, any customer-provided secrets embedded in config payloads) use envelope encryption with a data-encryption key wrapped by a KMS or Vault master key reference configured at deploy time. The persistence module never logs ciphertext, plaintext, or key material. Column naming convention: `*_ciphertext`, `*_dek_id`, `*_nonce`.

### Decision: Connection, pool, and backpressure rules

- Asyncpg connection pool per process, sized from Helm values; saturation exposed as a Prometheus metric.
- A per-query statement timeout enforced at the session level; long-running jobs use dedicated sessions with larger timeouts.
- Redis client is a single async connection per process with a bounded pool for pipelines; cluster mode is configurable.
- On shutdown, the FastAPI app and ARQ workers drain active sessions to a checkpoint boundary, then close pools; readiness probe flips to failing the moment drain begins.

### Decision: Tenant and team scoping is an interface invariant

Every repository, ledger, and store method that touches tenant data MUST accept a tenant context object (`tenant_id`, `team_id`, optional `project_id`) and MUST parameterise every query with it. Postgres `row_security_policy` is enabled on all tenant-scoped tables as a belt-and-suspenders measure; the application role connects with a GUC set to the tenant on each transaction. Cross-tenant queries exist only for platform-wide admin endpoints gated by RBAC.

### Decision: Observability and health surface

- Liveness probe: database reachable, Redis reachable, pool not exhausted.
- Readiness probe: migrations applied, active snapshot loaded, Redis subscriber connected.
- Metrics: pool-utilisation, pool-wait p95, query p95 per subsystem, Redis command p95, circuit-breaker state, DLQ depth, webhook-dedupe hit rate, budget-reservation denials, migration version.
- Alerts: pool saturation, migration drift, DLQ growth rate, circuit-breaker open, webhook replay burst, envelope-encryption key rotation overdue.
- Logs: structured with `tenant_id`, `team_id`, `run_id`, `subsystem`, `operation`; ciphertext fields are never logged; OpenTelemetry spans wrap every repository method.

## Risks / Trade-offs

- Risk: additional latency on every path that used to be a dict lookup. Mitigation: process-local caches for read-mostly data (handler registry, model catalog) invalidated via Redis pub/sub; async connection pools; measured and alerted via metrics.
- Risk: Redis outage impacts queue, circuit breaker, and idempotency. Mitigation: PostgreSQL is authoritative for budgets, DLQ, idempotency, and metering; Redis outage degrades to fail-closed policies; air-gapped deployments run Redis inside the same cluster and treat it as a first-class dependency.
- Risk: migration mistakes block deploys. Mitigation: expand/contract discipline, reversibility tests, shadow-mode validation for config schema changes, Alembic migrations gated by CI.
- Risk: envelope-encryption key rotation is error-prone. Mitigation: key ID column per row, rotation job that rewraps in the background, dual-read support during rotation, credential rotation SLA metric.
- Risk: test slowdown. Mitigation: keep `InMemory*` adapters as a fast test double; integration tests use ephemeral containers only where persistence semantics are under test.
- Trade-off: extra complexity around Redis and Postgres split for budgets. Justified by the Tier 1 "race-free reservations" non-negotiable.

## Migration Plan

1. Add `backend/src/backend/persistence/` with contracts (Protocols), a no-op factory, and a test double registry. Move existing `InMemory*` classes under `persistence/testing/`. This is a no-behavior-change refactor.
2. Ship Alembic baseline migration that creates the first set of tables (`runs`, `webhook_idempotency_records`). Wire migration runner into app startup with a kill switch for air-gapped pre-seeded databases.
3. Replace `InMemoryWebhookGuard` with the PostgreSQL-plus-Redis adapter; run in shadow mode first (both adapters compare results, logs mismatches) for one release.
4. Replace `InMemoryRunRepository` with the PostgreSQL-backed repository wired to the LangGraph PostgresSaver; cut over behind a feature flag.
5. Replace `InMemoryControlPlaneStore` and switch the handler registry to the snapshot-plus-Redis-invalidation pattern. Seed an initial snapshot during migration.
6. Replace `InMemoryWorkerController` and wire ARQ on Redis; add the durable DLQ table. Run chaos tests covering pod restart and worker drain.
7. Replace `InMemoryBudgetLedger` with the Redis-plus-PostgreSQL adapter; verify race-free decrement under load tests.
8. Replace `InMemoryMeteringLedger` and schedule the hourly rollup job.
9. Replace `InMemoryModelCatalog` and `InMemoryProviderHealthStore`; validate the air-gapped fallback path with Redis disabled in a dedicated test profile.
10. Remove production wiring for the `InMemory*` adapters; keep them available only through the test factory.
11. Update `helm/` values, `docs/` operator runbooks, DR drill evidence, and observability dashboards. Remove any residual references in archived OpenSpec changes only by forward-linking, not by editing archived files.

Each step lands behind a feature flag, is observable, and is individually reversible via `alembic downgrade` plus config flip.
