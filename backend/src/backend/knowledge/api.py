from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status

from backend.persistence.telemetry import PersistenceTelemetry

from .config import InternalRagSettings
from .service import (
    EmbeddingClient,
    KnowledgeDocument,
    KnowledgeDocumentCreate,
    KnowledgeDocumentUpdate,
    KnowledgeIngestionJob,
    KnowledgeIngestionService,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    KnowledgeRepository,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResponse,
    KnowledgeRetrievalService,
)


def build_knowledge_router(
    *,
    repository: KnowledgeRepository | None = None,
    settings: InternalRagSettings | None = None,
    telemetry: PersistenceTelemetry | None = None,
) -> APIRouter:
    repo = repository or KnowledgeRepository()
    resolved_settings = settings or InternalRagSettings.from_env()
    ingestion = KnowledgeIngestionService(
        repository=repo,
        embeddings=EmbeddingClient(resolved_settings),
        telemetry=telemetry,
    )
    retrieval = KnowledgeRetrievalService(repository=repo, telemetry=telemetry)
    router = APIRouter(prefix="/api/v1/admin/knowledge", tags=["knowledge"])

    @router.get("/documents", response_model=list[KnowledgeDocument])
    def list_documents(
        tenant_id: str,
        team_id: str,
        x_role: Annotated[str, Header(alias="X-Role")] = "admin",
    ) -> list[KnowledgeDocument]:
        _require_admin(x_role)
        return repo.list_documents(tenant_id=tenant_id, team_id=team_id)

    @router.post("/documents", response_model=KnowledgeDocument, status_code=status.HTTP_201_CREATED)
    def create_document(
        body: KnowledgeDocumentCreate,
        x_role: Annotated[str, Header(alias="X-Role")] = "admin",
    ) -> KnowledgeDocument:
        _require_admin(x_role)
        return repo.create_document(body)

    @router.put("/documents/{document_id}", response_model=KnowledgeDocument)
    def update_document(
        document_id: str,
        body: KnowledgeDocumentUpdate,
        x_role: Annotated[str, Header(alias="X-Role")] = "admin",
    ) -> KnowledgeDocument:
        _require_admin(x_role)
        document = repo.update_document(document_id, body)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge_document_not_found")
        return document

    @router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_document(
        document_id: str,
        x_role: Annotated[str, Header(alias="X-Role")] = "admin",
    ) -> Response:
        _require_admin(x_role)
        if not repo.delete_document(document_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge_document_not_found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/documents/{document_id}/ingest", response_model=KnowledgeIngestResponse)
    def ingest_document(
        document_id: str,
        body: KnowledgeIngestRequest,
        x_role: Annotated[str, Header(alias="X-Role")] = "admin",
    ) -> KnowledgeIngestResponse:
        _require_admin(x_role)
        document = repo.get_document(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge_document_not_found")
        if document.tenant_id != body.tenant_id or document.team_id != body.team_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="knowledge_document_tenant_mismatch")
        return ingestion.ingest(document, body)

    @router.post(
        "/documents/{document_id}/ingestion-jobs",
        response_model=KnowledgeIngestionJob,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def enqueue_ingestion_job(
        document_id: str,
        body: KnowledgeIngestRequest,
        x_role: Annotated[str, Header(alias="X-Role")] = "admin",
    ) -> KnowledgeIngestionJob:
        _require_admin(x_role)
        document = repo.get_document(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge_document_not_found")
        if document.tenant_id != body.tenant_id or document.team_id != body.team_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="knowledge_document_tenant_mismatch")
        return ingestion.enqueue(document, body)

    @router.get("/ingestion-jobs/{job_id}", response_model=KnowledgeIngestionJob)
    def get_ingestion_job(
        job_id: str,
        x_role: Annotated[str, Header(alias="X-Role")] = "admin",
    ) -> KnowledgeIngestionJob:
        _require_admin(x_role)
        job = repo.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="knowledge_ingestion_job_not_found")
        return job

    @router.post("/search", response_model=KnowledgeRetrievalResponse)
    def dry_run_search(
        body: KnowledgeRetrievalRequest,
        x_role: Annotated[str, Header(alias="X-Role")] = "admin",
    ) -> KnowledgeRetrievalResponse:
        _require_admin(x_role)
        try:
            return retrieval.retrieve(body)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    @router.post("/ingestion-jobs/{job_id}/run", response_model=KnowledgeIngestionJob)
    def run_ingestion_job(
        job_id: str,
        x_role: Annotated[str, Header(alias="X-Role")] = "admin",
    ) -> KnowledgeIngestionJob:
        _require_admin(x_role)
        try:
            return ingestion.process_job(job_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="knowledge_ingestion_job_not_found",
            ) from exc

    return router


def _require_admin(role: str) -> None:
    if role not in {"admin", "super_admin", "super-admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_role_required")
