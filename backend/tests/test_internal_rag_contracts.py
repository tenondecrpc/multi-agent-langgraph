from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.knowledge import (
    INTERNAL_RAG_FEATURE_FLAG,
    InternalRagSettings,
    KnowledgeRepository,
    persist_retrieval_summaries,
    probe_pgvector_extension,
)
from backend.knowledge.service import (
    EmbeddingClient,
    KnowledgeDocumentCreate,
    KnowledgeIngestionService,
    KnowledgeIngestRequest,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalService,
)
from backend.persistence.telemetry import bootstrap_telemetry
from backend.runtime import PlanningRequest, TicketRunState
from backend.worker import process_knowledge_ingestion


def test_internal_rag_feature_flag_is_registered_default_off() -> None:
    assert INTERNAL_RAG_FEATURE_FLAG.flag_id == "internal_rag_enabled"
    assert INTERNAL_RAG_FEATURE_FLAG.flag_type == "release"
    assert INTERNAL_RAG_FEATURE_FLAG.default_enabled is False
    assert INTERNAL_RAG_FEATURE_FLAG.auditable is True


def test_pgvector_probe_is_noop_when_flag_is_off() -> None:
    result = asyncio.run(probe_pgvector_extension(InternalRagSettings(enabled=False)))

    assert result.enabled is False
    assert result.ready is True
    assert result.reason is None


def test_pgvector_probe_fails_closed_when_enabled_without_database_url() -> None:
    result = asyncio.run(probe_pgvector_extension(InternalRagSettings(enabled=True, database_url=None)))

    assert result.enabled is True
    assert result.ready is False
    assert result.reason == "internal_rag_database_url_missing"


def test_readiness_fails_closed_when_internal_rag_enabled_without_pgvector_probe() -> None:
    with TestClient(create_app(internal_rag_settings=InternalRagSettings(enabled=True))) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert "internal_rag_database_url_missing" in response.json()["reasons"]


def test_admin_knowledge_document_crud_and_ingest_flow() -> None:
    repository = KnowledgeRepository()
    settings = InternalRagSettings(
        embedding_endpoint="http://embedding.internal/embed",
        embedding_model="local-test-embedder",
    )
    client = TestClient(create_app(knowledge_repository=repository, internal_rag_settings=settings))

    created = client.post(
        "/api/v1/admin/knowledge/documents",
        headers={"X-Role": "admin"},
        json={
            "tenant_id": "tenant-alpha",
            "team_id": "team-core",
            "repo_id": "repo-main",
            "title": "Login patterns",
            "source_type": "runbook",
            "source_uri": "docs/runbooks/login.md",
            "content_sha256": "a" * 64,
            "created_by": "operator@example.com",
        },
    )
    assert created.status_code == 201
    document = created.json()

    listed = client.get(
        "/api/v1/admin/knowledge/documents",
        headers={"X-Role": "admin"},
        params={"tenant_id": "tenant-alpha", "team_id": "team-core"},
    )
    assert listed.status_code == 200
    assert [item["document_id"] for item in listed.json()] == [document["document_id"]]

    updated = client.put(
        f"/api/v1/admin/knowledge/documents/{document['document_id']}",
        headers={"X-Role": "admin"},
        json={"title": "Login implementation patterns"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Login implementation patterns"

    ingested = client.post(
        f"/api/v1/admin/knowledge/documents/{document['document_id']}/ingest",
        headers={"X-Role": "admin"},
        json={
            "tenant_id": "tenant-alpha",
            "team_id": "team-core",
            "content": "Use accessible labels.\nKeep auth errors generic.",
            "chunk_size": 200,
        },
    )
    assert ingested.status_code == 200
    payload = ingested.json()
    assert payload["job"]["status"] == "completed"
    assert payload["job"]["embedding_endpoint"] == "http://embedding.internal/embed"
    assert payload["job"]["embedding_model"] == "local-test-embedder"
    assert payload["job"]["total_chunks"] == 1
    assert payload["chunks"][0]["tenant_id"] == "tenant-alpha"

    dry_run = client.post(
        "/api/v1/admin/knowledge/search",
        headers={"X-Role": "admin"},
        json={
            "tenant_id": "tenant-alpha",
            "team_id": "team-core",
            "role": "planner",
            "query": "accessible labels",
        },
    )
    assert dry_run.status_code == 200
    assert dry_run.json()["role"] == "planner"
    assert dry_run.json()["hits"][0]["document_id"] == document["document_id"]

    deleted = client.delete(
        f"/api/v1/admin/knowledge/documents/{document['document_id']}",
        headers={"X-Role": "admin"},
    )
    assert deleted.status_code == 204


def test_admin_knowledge_endpoints_require_admin_role() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/admin/knowledge/documents",
        headers={"X-Role": "viewer"},
        json={
            "tenant_id": "tenant-alpha",
            "team_id": "team-core",
            "title": "Denied",
            "source_type": "runbook",
            "source_uri": "docs/denied.md",
            "content_sha256": "b" * 64,
            "created_by": "viewer@example.com",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "admin_role_required"


def test_knowledge_ingestion_jobs_are_resumable_and_emit_progress_metrics() -> None:
    repository = KnowledgeRepository()
    settings = InternalRagSettings(
        embedding_endpoint="http://embedding.internal/embed",
        embedding_model="local-test-embedder",
    )
    telemetry = bootstrap_telemetry()
    service = KnowledgeIngestionService(
        repository=repository,
        embeddings=EmbeddingClient(settings),
        telemetry=telemetry,
    )
    document = repository.create_document(
        KnowledgeDocumentCreate(
            tenant_id="tenant-alpha",
            team_id="team-core",
            title="Testing patterns",
            source_type="runbook",
            source_uri="docs/testing.md",
            content_sha256="c" * 64,
            created_by="operator@example.com",
        )
    )

    queued = service.enqueue(
        document,
        KnowledgeIngestRequest(
            tenant_id="tenant-alpha",
            team_id="team-core",
            content="A" * 450,
            chunk_size=200,
        ),
    )
    assert queued.status == "queued"

    processed_payload = asyncio.run(
        process_knowledge_ingestion({"knowledge_ingestion_service": service}, queued.job_id)
    )
    assert processed_payload["status"] == "completed"
    assert processed_payload["total_chunks"] == 3
    assert processed_payload["processed_chunks"] == 3

    resumed_payload = asyncio.run(
        process_knowledge_ingestion({"knowledge_ingestion_service": service}, queued.job_id)
    )
    assert resumed_payload["status"] == "completed"
    assert len(repository.chunks) == 3

    metrics = telemetry.render_prometheus()
    assert "devsquad_knowledge_ingestion_progress_ratio" in metrics
    assert "devsquad_knowledge_ingestion_jobs_total" in metrics


def test_runtime_retrieval_is_tenant_scoped_and_role_whitelisted() -> None:
    repository = KnowledgeRepository()
    settings = InternalRagSettings(embedding_model="local-test-embedder")
    telemetry = bootstrap_telemetry()
    service = KnowledgeIngestionService(
        repository=repository,
        embeddings=EmbeddingClient(settings),
    )
    allowed_document = repository.create_document(
        KnowledgeDocumentCreate(
            tenant_id="tenant-alpha",
            team_id="team-core",
            title="Login patterns",
            source_type="runbook",
            source_uri="docs/login.md",
            content_sha256="d" * 64,
            created_by="operator@example.com",
        )
    )
    other_document = repository.create_document(
        KnowledgeDocumentCreate(
            tenant_id="tenant-beta",
            team_id="team-core",
            title="Other tenant login patterns",
            source_type="runbook",
            source_uri="docs/other-login.md",
            content_sha256="e" * 64,
            created_by="operator@example.com",
        )
    )
    service.ingest(
        allowed_document,
        KnowledgeIngestRequest(
            tenant_id="tenant-alpha",
            team_id="team-core",
            content="Login forms require accessible labels.",
        ),
    )
    service.ingest(
        other_document,
        KnowledgeIngestRequest(
            tenant_id="tenant-beta",
            team_id="team-core",
            content="Login forms in another tenant must never leak.",
        ),
    )

    retrieval = KnowledgeRetrievalService(repository=repository, telemetry=telemetry)
    response = retrieval.retrieve(
        KnowledgeRetrievalRequest(
            tenant_id="tenant-alpha",
            team_id="team-core",
            role="planner",
            query="login labels",
        )
    )

    assert [hit.tenant_id for hit in response.hits] == ["tenant-alpha"]
    assert response.hits[0].document_id == allowed_document.document_id
    metrics = telemetry.render_prometheus()
    assert "devsquad_knowledge_retrieval_latency_seconds" in metrics
    assert "devsquad_knowledge_retrieval_hit_ratio" in metrics
    assert "devsquad_knowledge_excerpt_size_chars" in metrics

    try:
        retrieval.retrieve(
            KnowledgeRetrievalRequest(
                tenant_id="tenant-alpha",
                team_id="team-core",
                role="coder",
                query="login",
            )
        )
    except PermissionError as exc:
        assert str(exc) == "knowledge_retrieval_denied:coder"
    else:
        raise AssertionError("coder retrieval should be denied")


def test_retrieved_excerpt_summaries_are_persisted_in_run_state() -> None:
    repository = KnowledgeRepository()
    service = KnowledgeIngestionService(
        repository=repository,
        embeddings=EmbeddingClient(InternalRagSettings()),
    )
    document = repository.create_document(
        KnowledgeDocumentCreate(
            tenant_id="tenant-alpha",
            team_id="team-core",
            title="Review patterns",
            source_type="runbook",
            source_uri="docs/review.md",
            content_sha256="f" * 64,
            created_by="operator@example.com",
        )
    )
    service.ingest(
        document,
        KnowledgeIngestRequest(
            tenant_id="tenant-alpha",
            team_id="team-core",
            content="Reviewers compare the implementation to pinned planner artifacts.",
        ),
    )
    response = KnowledgeRetrievalService(repository=repository).retrieve(
        KnowledgeRetrievalRequest(
            tenant_id="tenant-alpha",
            team_id="team-core",
            role="reviewer",
            query="reviewers planner artifacts",
        )
    )
    run = TicketRunState.new(PlanningRequest(summary="Use retrieved review guidance"))

    persist_retrieval_summaries(run, response, max_excerpt_chars=32)

    assert len(run.knowledge_excerpts) == 1
    assert run.knowledge_excerpts[0].document_id == document.document_id
    assert run.knowledge_excerpts[0].excerpt == "Reviewers compare the implementa"
