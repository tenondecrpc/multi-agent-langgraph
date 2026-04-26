# Internal RAG Via pgvector Runbook

## Scope

This runbook covers the optional `internal_rag_enabled` capability. The feature is default off, tenant-scoped, read-only during ticket execution, and backed by PostgreSQL plus `pgvector`. Do not add a separate vector datastore.

## Enablement

1. Confirm PostgreSQL has the `vector` extension available and migrations are current.
2. Deploy Helm values with:
   - `internalRag.enabled: "false"` for initial rollout.
   - `internalRag.embeddingEndpoint` pointing at the customer-owned embedding endpoint.
   - `internalRag.embeddingModel` set to the approved self-hosted or connected-profile model.
3. In `air_gapped`, confirm `helm template dev-squad ./helm -f ./helm/values.yaml -f ./helm/values-air-gapped.yaml` renders a NetworkPolicy that allows only the in-cluster embedding pod selector.
4. Turn on `internal_rag_enabled` for one staging tenant through the feature-flag control plane.
5. Check `/readyz`. If `internal_rag_pgvector_missing` or `internal_rag_pgvector_probe_failed` appears, turn the flag off and investigate database extension state.
6. Ingest a non-sensitive test document through `/api/v1/admin/knowledge/documents` and `/api/v1/admin/knowledge/documents/{id}/ingestion-jobs`.
7. Run `/api/v1/admin/knowledge/search` as an admin using planner and reviewer roles.

## Rollback

1. Turn `internal_rag_enabled` off for the affected tenant.
2. Confirm new runtime retrieval attempts stop and ticket execution continues without internal knowledge context.
3. If readiness is failing, set `internalRag.enabled: "false"` in Helm and roll back the release.
4. Do not drop `pgvector` during emergency rollback; it may be shared by other schemas. The app migration downgrade drops only application-owned knowledge tables.

## Retention And Deletion

- Knowledge documents and chunks inherit tenant retention and deletion policy.
- Tenant deletion must remove `knowledge_documents`, `knowledge_chunks`, and `knowledge_ingestion_jobs` rows for that tenant.
- Re-ingestion should create new chunks from approved sources rather than mutating runtime state.
- Retrieved excerpts persisted in run state follow run-retention rules and must remain auditable for resumes and reviews.

## Metrics

- `devsquad_knowledge_ingestion_progress_ratio`
- `devsquad_knowledge_ingestion_jobs_total`
- `devsquad_knowledge_retrieval_latency_seconds`
- `devsquad_knowledge_retrieval_hit_ratio`
- `devsquad_knowledge_excerpt_size_chars`

## Escalation

Escalate to `security_review` if search results show cross-tenant data, if runtime agents attempt ingestion, or if air-gapped deployments attempt vendor embedding egress.
