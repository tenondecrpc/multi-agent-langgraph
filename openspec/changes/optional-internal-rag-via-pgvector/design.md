# Design: Optional Internal RAG Via pgvector

## Context

Extending PostgreSQL with `pgvector` is the only sanctioned path to internal RAG. The capability stays off by default and must respect tenant scoping, read-only semantics during ticket execution, and role whitelist.

## Goals / Non-Goals

### Goals

- Feature-flagged, tenant-scoped knowledge ingestion and retrieval.
- Read-only retrieval during ticket execution.
- Role whitelist for retrieval calls.
- Works in air-gapped deployments with a self-hosted embedding model.

### Non-Goals

- No vendor-hosted embedding or vector service.
- No re-ingestion inside the ticket pipeline (writes happen via admin API only).

## Decisions

### Decision: Feature flag and capability probe

`internal_rag_enabled` flag in the control plane governs the surface. On boot, the backend probes `pgvector` availability and fails closed if the flag is on and the extension is not present.

### Decision: Schema and HNSW index

`knowledge_chunks.embedding vector(n)` carries the embedding; HNSW index tuned for recall. Tenant scoping via row-level security and composite index `(tenant_id, doc_id, chunk_id)`.

### Decision: Role whitelist during ticket execution

Only planner and reviewer may call retrieval during a run. Coder and pr_creator are denied. The admin dry-run endpoint is reserved for operators and is not callable from runtime agents.

### Decision: Excerpt persistence

Each retrieval during a run persists the excerpt summary (truncated text, chunk ids, distance) into the run state for audit and reproducibility.

### Decision: Air-gapped embedding

When connected, embeddings call an operator-configured embedding endpoint. In air-gapped mode, the endpoint is a self-hosted model in-cluster; no vendor call is attempted.

## Risks / Trade-offs

- HNSW build time on large corpora. Mitigated by background ingestion jobs with progress metrics.
- Retrieval latency variance. Mitigated by configurable k and operator-tunable search parameters.
- Data leakage across tenants. Mitigated by RLS and composite-index scoping enforced in every query.

## Migration Plan

1. Enable `pgvector` extension in staging with flag off.
2. Add schema and admin ingestion endpoints; flag remains off.
3. Enable planner and reviewer retrieval under flag in staging.
4. Customer opt-in per tenant in production; runtime guarded by flag and by role whitelist.
