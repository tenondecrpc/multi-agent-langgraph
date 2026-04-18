## 1. Artifact Finalisation And Alignment

- [ ] 1.1 Review `proposal.md`, `design.md`, and every file under `specs/` for alignment with `openspec/config.yaml` and `AGENTS.md`; confirm no Tier 1 rule is weakened and every risky change is explicitly flagged (schema, Helm, secrets, feature flags).
- [ ] 1.2 Confirm the list of modified capabilities matches existing spec folders under `openspec/specs/`; reconcile naming mismatches before implementation.
- [ ] 1.3 Record the decision on whether the optional `pgvector` capability is in scope for this change or explicitly deferred, and update the proposal accordingly if needed.

## 2. Persistence Module Scaffolding

- [ ] 2.1 Create `backend/src/backend/persistence/` with submodules `contracts.py` (Protocols), `factory.py` (DI), `db.py` (asyncpg and SQLAlchemy), `redis.py` (client factory), `encryption.py` (envelope encryption), `health.py`, and `testing/` for the in-memory test doubles.
- [ ] 2.2 Move the existing `InMemory*` classes (`runtime/store.py`, `control_plane/store.py`, `control_plane/graph.py`, `platform/queue.py`, `governance/budget.py`, `governance/metering.py`, `governance/catalog.py`, `governance/routing.py`, `security/webhook.py`) under `persistence/testing/` behind the new Protocols as a no-behavior-change refactor.
- [ ] 2.3 Wire `backend/src/backend/app.py` and ARQ worker bootstrap to obtain adapters from the persistence factory; reject any remaining direct construction of `InMemory*` adapters in production code paths via a lint rule or unit test.
- [ ] 2.4 Add dependencies via `uv`: `asyncpg`, `SQLAlchemy` async, `alembic`, `redis` async, `langgraph-checkpoint-postgres`, `langgraph.store.postgres`; run `uv sync --project backend --dev`.

## 3. Migration Framework And Baseline Schema

- [ ] 3.1 Add Alembic to the backend, wire the migration runner into app startup with a kill switch for air-gapped pre-seeded databases, and document operator usage in `docs/`.
- [ ] 3.2 Write a reversibility test harness that runs `alembic upgrade head` and `alembic downgrade -1` against an ephemeral PostgreSQL and asserts lossless round-trip for seeded rows.
- [ ] 3.3 Author the baseline migration creating `runs`, `webhook_idempotency_records`, and the shared tenant-context infrastructure (row-level security policies, session GUC usage), and its reversibility test.

## 4. Webhook Guard (First Cutover)

- [ ] 4.1 Implement the PostgreSQL-plus-Redis `WebhookGuard` adapter: durable insert with unique constraint on `(source, delivery_id)`, Redis short-window dedupe cache with TTL equal to freshness window, tenant and team metadata recorded.
- [ ] 4.2 Add shadow-mode wrapper that runs the old and new adapters in parallel, compares results, and logs mismatches without affecting behavior; enable in one release before cutover.
- [ ] 4.3 Cut over behind a feature flag; verify HMAC freshness remains the first-line defense and idempotency checks align with spec scenarios.
- [ ] 4.4 Add unit tests, an integration test using ephemeral PostgreSQL and Redis, and a chaos test for Redis outage (PostgreSQL unique constraint still rejects duplicates).

## 5. Run Repository And LangGraph PostgresSaver

- [ ] 5.1 Implement `RunRepository` adapter backed by PostgreSQL and the LangGraph `PostgresSaver`; tenant-scope every query; persist pause and resume transitions atomically with the checkpoint.
- [ ] 5.2 Migrate seed data and verify pod-restart resumption in an integration test that kills a worker mid-run.
- [ ] 5.3 Add observability spans and metrics; confirm `runs` table row-level security blocks cross-tenant access.
- [ ] 5.4 Remove production wiring of `InMemoryRunRepository`; keep it available only via the test factory.

## 6. Control-Plane Store And Handler Registry

- [ ] 6.1 Implement PostgreSQL-backed `ControlPlaneStore` with tables for graph versions, agent versions, snapshots, run-snapshot bindings, shadow reports, and audit events; enforce append-only semantics on audit events at the schema or role level.
- [ ] 6.2 Add optimistic concurrency for activations and rollbacks with typed conflict errors and audit rows.
- [ ] 6.3 Implement snapshot-driven `HandlerRegistry` with a process-local cache keyed by `snapshot_id` and invalidation via a Redis pub/sub channel `control_plane:snapshot_activated`.
- [ ] 6.4 Integration tests for two-operator concurrent activation, rollback, cache invalidation freshness SLO, and pinned-run stability across activation.
- [ ] 6.5 Remove production wiring of `InMemoryControlPlaneStore` and `InMemoryHandlerRegistry`.

## 7. Worker Queue, Weighted-Fair Dispatch, And DLQ

- [ ] 7.1 Replace `InMemoryWorkerController` with an ARQ-on-Redis transport; wire the existing weighted-fair dispatcher to Redis-backed per-tenant in-flight counters.
- [ ] 7.2 Add the durable `dead_letter_records` table with retention aligned to the data-retention policy; wire DLQ writes into the terminal-failure path.
- [ ] 7.3 Implement Redis drain-lease coordination: worker acquires lease on SIGTERM, refuses new assignments, flushes to checkpoint boundary, persists `checkpoint_ref`, releases lease.
- [ ] 7.4 Chaos tests: pod kill mid-job, Redis outage and recovery (DLQ records remain queryable), tenant concurrency cap respected across replicas, starvation threshold fires.

## 8. Budget Ledger With Race-Free Reservations

- [ ] 8.1 Implement the `BudgetLedger` adapter using a Redis Lua script for atomic decrement and check, with write-through to durable PostgreSQL tables `budget_reservations`, `budget_charges`, `budget_denials` in the same unit of work.
- [ ] 8.2 Implement reconciliation from PostgreSQL to Redis on Redis recovery; add a reconciliation integration test.
- [ ] 8.3 Concurrent reservation load test: N workers race against a per-team cap, assert no overage and exactly one winner per contested reservation.
- [ ] 8.4 Remove production wiring of `InMemoryBudgetLedger`.

## 9. Metering, Hourly Rollups, And CSV Export

- [ ] 9.1 Implement `MeteringLedger` writing to a time-partitioned `metering_facts` table; add tenant-scoped indexes and retention policy wiring.
- [ ] 9.2 Implement the scheduled ARQ rollup job producing `metering_hourly_rollups`; add idempotent backfill support.
- [ ] 9.3 Update CSV export to read from `metering_hourly_rollups`; document the Tier 2 degradation explicitly in `docs/`.
- [ ] 9.4 Reconciliation test: CSV export totals match the sum over `metering_facts` within the declared tolerance.
- [ ] 9.5 Follow-up parity task: track rate-card reconciliation (Tier 2 full goal) as a deferred backlog item with a link back to this change.

## 10. Model Catalog And Provider Health

- [ ] 10.1 Implement PostgreSQL-backed `ModelCatalog` with a bundled YAML shipped in the container image; boot reconciliation with audit events for differences.
- [ ] 10.2 Implement the Redis-shared circuit breaker for providers using a Lua script; persist incident evidence in `provider_health_events` for audit.
- [ ] 10.3 Air-gapped test profile: boot with Redis unreachable, verify fail-closed behavior and observable alerts; verify catalog seeding from bundled YAML.
- [ ] 10.4 Remove production wiring of `InMemoryModelCatalog` and `InMemoryProviderHealthStore`.

## 11. Tenant Isolation And Envelope Encryption

- [ ] 11.1 Enable PostgreSQL row-level security on every tenant-scoped table; configure session tenant GUC in the persistence module; add a negative test for cross-tenant reads.
- [ ] 11.2 Implement envelope encryption helpers; integrate with KMS or Vault per Helm values; add rotation job with dual-read support and a key-rotation SLA metric.
- [ ] 11.3 Scrub logs and metrics: add a lint-style test that fails if any log record contains ciphertext-like payloads, plaintext secret field names, or key material.

## 12. Observability, Health, And Alerts

- [ ] 12.1 Add Prometheus metrics listed in `design.md` (pool utilisation and wait p95, query p95 per subsystem, Redis command p95, circuit-breaker state, DLQ depth, webhook-dedupe hit rate, budget-reservation denials, migration version).
- [ ] 12.2 Wire OpenTelemetry spans to every repository, ledger, and guard method with `tenant_id`, `team_id`, `run_id`, `subsystem`, `operation` attributes.
- [ ] 12.3 Add liveness and readiness probes backed by the persistence health surface; readiness flips on migration drift and on loss of active snapshot.
- [ ] 12.4 Add alert rules, dashboards, and runbooks under `docs/`; include DLQ-growth and breaker-open runbooks.

## 13. Admin UI Status Panel (Accessibility Non-Negotiable Subset)

- [ ] 13.1 Surface migration version, applied version, active snapshot id, and persistence adapter readiness in the admin UI status panel.
- [ ] 13.2 Verify the non-negotiable accessibility subset: no color-only state, keyboard reachability of every control, `prefers-reduced-motion` support, AA text contrast.
- [ ] 13.3 Record a short manual-verification note or screenshot in the PR description.

## 14. Helm, Kustomize, And Deployment Profiles

- [ ] 14.1 Add Helm values for PostgreSQL and Redis connection URLs, pool sizes, TLS, statement timeouts, and envelope-encryption KMS or Vault references; provide separate defaults for connected and `air_gapped` profiles.
- [ ] 14.2 Integrate External Secrets Operator entries for database and Redis credentials; forbid credentials in environment variables checked into Git.
- [ ] 14.3 Dry-run and shadow-mode output for Helm changes; document in the PR description as high-risk.

## 15. Disaster Recovery And DR Drill Evidence

- [ ] 15.1 Extend backup and restore automation to cover the new tables; verify RPO and RTO against constitution targets.
- [ ] 15.2 Quarterly DR drill playbook update and first rehearsed drill; attach the drill report as audit evidence.
- [ ] 15.3 Redis outage drill update: verify fail-closed paths, reconciliation, and adapter recovery.

## 16. Verification And Release

- [ ] 16.1 Run `uv run --project backend ruff check backend/src backend/tests` and `uv run --project backend pytest` (including new integration and chaos tests); all green before merge.
- [ ] 16.2 Confirm the graph still traverses implementation, tests, diff guard, forbidden-path guard, review, and pre-PR sync before PR creation via an E2E smoke test.
- [ ] 16.3 Progressive delivery rollout with Argo Rollouts: canary, monitor persistence metrics and burn-rate alerts, automated rollback on SLO breach.
- [ ] 16.4 Feature-flag kill switches validated for: new webhook guard, new run repository, new control-plane store, new worker controller, new budget ledger, new metering ledger, new model catalog, new provider health store.

## 17. Cleanup And Archive

- [ ] 17.1 Delete production wiring for every `InMemory*` adapter; retain them only under `persistence/testing/` for unit tests.
- [ ] 17.2 Update `docs/` operator and integrator guides with the final persistence topology, RPO, RTO, and runbooks.
- [ ] 17.3 Archive this change via `openspec-archive-change` only after implementation, tests, review, DR drill evidence, and parity backlog entries are in place.
