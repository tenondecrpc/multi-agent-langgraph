## Why

The constitution lists optional internal knowledge retrieval as a Tier 2 extension that, when enabled, must stay tenant-scoped, read-only during ticket execution, and reuse PostgreSQL via `pgvector`. PLAN.md includes knowledge-base CRUD, ingest pipeline, HNSW-indexed retrieval, role whitelist, and an admin dry-run search. This change specifies the capability behind a feature flag so a customer can enable it without violating invariants or introducing a new datastore.

## What Changes

- Enable `pgvector` as an optional PostgreSQL extension, controlled by a feature flag and Helm values.
- Add tenant-scoped knowledge-base CRUD and ingest endpoints in the admin API; chunking and embedding pipeline runs inside the customer-owned cluster.
- Implement HNSW-indexed retrieval scoped to the active tenant; planner and reviewer are the only roles whitelisted to query during ticket execution; retrieval is strictly read-only during runs.
- Persist retrieved excerpts into the run state for audit and for reproducibility.
- Admin dry-run search endpoint for operator testing without triggering ticket execution.
- Default is OFF at GA; documentation and runbooks cover enablement, rollback, and retention.

## Capabilities

### New Capabilities

- `internal-rag-via-pgvector`: feature-flagged capability for tenant-scoped knowledge ingestion, HNSW retrieval, role whitelist, excerpt persistence, and admin dry-run.

### Modified Capabilities

- `context-resolution-policy`: adds optional internal knowledge as step 4 in the local-first resolution order when the flag is enabled.

## Impact

- Code: new `backend/src/backend/knowledge/` module; admin API endpoints; planner and reviewer integration points.
- Schema: `knowledge_documents`, `knowledge_chunks` with `embedding vector(n)`, `knowledge_ingestion_jobs`.
- Deployment: Helm values to enable `pgvector`; air-gapped profile supports the feature without vendor embeddings (use self-hosted embedding model).
- Observability: ingestion-job metrics, retrieval-latency p95, retrieval-hit rate per tenant.
- Tests: unit, integration (pgvector), and privacy tests verifying no cross-tenant retrieval.
- Constitution alignment: Tier 2 optional extension; default OFF; no new datastore.
