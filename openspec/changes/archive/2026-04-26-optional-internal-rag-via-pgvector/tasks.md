## 1. Artifact Alignment

- [x] 1.1 Compose with the active persistence change and the feature-flag work from `progressive-delivery-and-feature-flag-kill-switches`.

## 2. Schema And Extension

- [x] 2.1 Enable `pgvector` via Alembic migration with reversibility test; add `knowledge_documents`, `knowledge_chunks`, `knowledge_ingestion_jobs`.
- [x] 2.2 Tenant-scope everything; enable row-level security.

## 3. Feature Flag

- [x] 3.1 Register `internal_rag_enabled` flag; default OFF; boot probe for extension presence.

## 4. Ingestion Pipeline

- [x] 4.1 Admin API CRUD and ingest endpoints; chunking and embedding using operator-configured endpoint.
- [x] 4.2 Background ARQ ingestion jobs with progress metrics and resumability.

## 5. Retrieval

- [x] 5.1 HNSW-indexed retrieval; role whitelist; read-only during runs.
- [x] 5.2 Persist excerpt summaries in run state.
- [x] 5.3 Admin dry-run search endpoint for operators.

## 6. Air-Gapped Support

- [x] 6.1 Self-hosted embedding endpoint in Helm values; NetworkPolicy denies vendor egress in air-gapped profile.

## 7. Observability

- [x] 7.1 Metrics: ingestion progress, retrieval-latency p95, retrieval-hit rate, excerpt-size distribution.
- [x] 7.2 Runbook covering enablement, rollback, and retention.

## 8. Verification

- [x] 8.1 `uv run --project backend pytest` including tenant-scope negative tests and air-gapped dry-run.
- [x] 8.2 Accessibility non-negotiable subset verified on the admin UI surfaces.

## 9. Archive

- [x] 9.1 Archive only after at least one customer has enabled the flag in staging and produced an evidence bundle.
