## Why

The current backend implements every stateful subsystem (ticket run repository, control-plane config store, agent handler registry, worker controller and DLQ, budget ledger, metering ledger, model catalog, provider health store, webhook idempotency guard) as in-process `InMemory*` classes. State is lost on pod restart, cannot be shared across horizontally-scaled FastAPI and ARQ workers, and cannot be audited, backed up, or restored. Several Tier 1 non-negotiables (parallel ticket processing, Redis-shared circuit breaker, race-free budget reservations, DLQ, graceful shutdown to checkpoint boundaries, DR with RPO and RTO, config versioning and rollback, audit trail) cannot be met without real persistence. This change introduces the durable persistence backbone that the constitution already assumes, using only PostgreSQL (with optional `pgvector`) and Redis, consistent with the stack already declared in `AGENTS.md` and `openspec/config.yaml`.

## What Changes

- Introduce a `durable-persistence-backbone` capability that defines the repository, ledger, and coordination interfaces, the PostgreSQL and Redis adapter contracts, tenant and team scoping rules, envelope-encryption boundaries, and the expand/contract migration discipline all modules must follow.
- Replace `InMemoryRunRepository` with a PostgreSQL-backed repository that persists `TicketRunState`, escalation bindings, and pause/resume transitions inside a LangGraph `PostgresSaver` checkpoint boundary.
- Replace `InMemoryControlPlaneStore` with PostgreSQL-backed tables for graph versions, agent versions, snapshots, run-snapshot bindings, shadow reports, and audit events, with optimistic concurrency and immutable audit append.
- Replace `InMemoryHandlerRegistry` usage in the control-plane graph with a registry that resolves from the active PostgreSQL snapshot and is cached per process with a Redis-pub-sub invalidation channel.
- Replace `InMemoryWorkerController`, weighted-fair dispatch state, and DLQ storage with ARQ on Redis 7 Cluster for queueing, a PostgreSQL `dead_letter_records` table for durable DLQ, and Redis-backed drain leases and in-flight counters.
- Replace `InMemoryBudgetLedger` with PostgreSQL-durable budget records plus Redis reservations guarded by Lua scripts so per-ticket and per-team caps are race-free across workers.
- Replace `InMemoryMeteringLedger` with PostgreSQL-durable metering facts feeding hourly rollups and CSV export (Tier 2 degradation already authorized).
- Replace `InMemoryModelCatalog` and `InMemoryProviderHealthStore` with PostgreSQL for catalog-of-record and Redis for the shared circuit-breaker health state; include an air-gapped-safe fallback table.
- Replace `InMemoryWebhookGuard` with a PostgreSQL idempotency table (HMAC digest, tenant, received-at, status) and a Redis short-window deduplication cache.
- Add a persistence health surface (liveness, readiness, migration status) wired into existing observability and DR runbooks; graceful shutdown must flush to Postgres and ARQ checkpoint boundaries.
- Keep all existing `InMemory*` classes available only as test doubles behind a common interface; production factories must never instantiate them.
- **BREAKING** for internal callers that construct `InMemory*` classes directly: they must now obtain instances from the persistence factory (DI container) and pass tenant and team context.

## Capabilities

### New Capabilities

- `durable-persistence-backbone`: cross-cutting contract for repositories, ledgers, queues, pub/sub, caches, and idempotency stores. Defines interface boundaries, PostgreSQL and Redis adapter rules, tenant and team scoping, envelope encryption at the application layer, expand/contract migration discipline, connection pooling, health probes, backup and restore hooks, and the prohibition on introducing any new production datastore.

### Modified Capabilities

- `ticket-execution-state`: run state, pause/resume, and escalation bindings must be persisted in PostgreSQL via the LangGraph Postgres checkpointer; no in-memory-only run storage is permitted on the success path.
- `worker-queue-operations`: queueing, weighted-fair dispatch, drain leases, in-flight counters, and DLQ must be backed by ARQ on Redis for transport and PostgreSQL for durable DLQ and audit; graceful shutdown must flush to checkpoint boundaries.
- `config-versioning-and-rollback`: graph and agent versions, snapshots, activations, shadow reports, and audit events must live in PostgreSQL with versioned rows, rollback, and shadow-mode validation; optimistic concurrency is mandatory.
- `agent-configuration-governance`: agent handler registry must resolve from the persisted active snapshot and invalidate via Redis pub/sub on activation or rollback.
- `graph-configuration-runtime`: the runtime graph must load its configuration from the persisted active snapshot; no process-local authoritative copy is allowed.
- `budget-governance`: per-ticket and per-team budget reservations must be race-free across workers using Redis atomic primitives with PostgreSQL as the durable ledger.
- `llm-metering-and-billing`: metering facts must be durably stored in PostgreSQL and feed hourly rollups; CSV export remains the Tier 2 degradation fallback.
- `model-catalog-and-token-caps`: the model catalog-of-record must live in PostgreSQL with a deterministic bundled fallback for air-gapped deployments.
- `provider-routing-and-failover`: provider health and the circuit breaker must be shared across workers via Redis, with fallback behavior that remains safe when Redis is unreachable in air-gapped mode.
- `webhook-and-api-protection`: webhook idempotency and replay protection must be backed by PostgreSQL for durable records and Redis for the short-window cache; HMAC freshness checks remain unchanged.
- `disaster-recovery-and-high-availability`: backup, restore drill, RPO, and RTO coverage must include the new persistence surfaces for all of the above.
- `observability-and-incident-response`: persistence health, migration status, connection-pool saturation, Redis circuit-breaker state, and DLQ depth must appear as structured logs, metrics, and alerts.

## Impact

- Code: `backend/src/backend/runtime/store.py`, `backend/src/backend/control_plane/store.py`, `backend/src/backend/control_plane/graph.py`, `backend/src/backend/platform/queue.py`, `backend/src/backend/governance/{budget,metering,catalog,routing}.py`, `backend/src/backend/security/webhook.py`, plus the FastAPI app and ARQ worker entry points under `backend/src/backend/app.py` and the platform API module. A new `backend/src/backend/persistence/` module hosts adapters, repositories, migrations, and the DI wiring.
- Dependencies: add `asyncpg`, `SQLAlchemy 2.x` async, `alembic`, `redis` async client, `langgraph-checkpoint-postgres`, `langgraph.store.postgres`; keep `arq` already declared.
- Schema: new PostgreSQL tables and indexes for runs, control-plane versions and snapshots, audit, budget ledger, metering facts, model catalog, DLQ, webhook idempotency; introduced via expand/contract Alembic migrations with reversibility tests.
- Secrets and config: database URLs, Redis URLs, KMS or Vault references must flow through External Secrets Operator; envelope-encryption keys must never touch application logs or config files.
- Deployment: Helm values and manifests under `helm/` must expose PostgreSQL and Redis connection configuration, pool sizing, TLS, and air-gapped-safe defaults; both connected and `air_gapped` profiles are first-class.
- Tests: new unit tests against the persistence interfaces, integration tests against ephemeral PostgreSQL and Redis (testcontainers or equivalent) under `backend/tests/`, plus chaos and failure-injection tests for DLQ, provider failover, and graceful shutdown.
- Observability: new metrics (pool saturation, query p95, Redis command latency, circuit-breaker state, DLQ depth, migration status), new alerts, and updated runbooks under `docs/`.
- Operator docs: update `docs/` with backup, restore, RPO and RTO guidance, migration runbook, and air-gapped deployment notes.
- Constitution alignment: Tier 1 non-negotiables are preserved and more fully met; no Tier 1 rule is weakened. No new production datastore is introduced beyond PostgreSQL (with optional `pgvector`) and Redis already listed in `AGENTS.md`.
