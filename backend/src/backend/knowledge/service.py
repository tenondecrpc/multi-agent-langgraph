from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter

from pydantic import BaseModel, Field

from backend.persistence.telemetry import PersistenceTelemetry

from .config import InternalRagSettings


class KnowledgeDocumentCreate(BaseModel):
    tenant_id: str
    team_id: str
    repo_id: str | None = None
    title: str
    source_type: str
    source_uri: str
    source_version: str | None = None
    content_sha256: str
    metadata: dict[str, object] = Field(default_factory=dict)
    created_by: str


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = None
    source_version: str | None = None
    active: bool | None = None
    metadata: dict[str, object] | None = None


class KnowledgeDocument(BaseModel):
    document_id: str
    tenant_id: str
    team_id: str
    repo_id: str | None
    title: str
    source_type: str
    source_uri: str
    source_version: str | None
    content_sha256: str
    metadata: dict[str, object]
    active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class KnowledgeIngestRequest(BaseModel):
    tenant_id: str
    team_id: str
    content: str
    chunk_size: int = Field(default=1200, ge=200, le=8000)
    embedding_model: str | None = None


class KnowledgeChunk(BaseModel):
    chunk_id: str
    tenant_id: str
    team_id: str
    document_id: str
    chunk_index: int
    source_type: str
    content: str
    content_sha256: str
    embedding_model: str
    embedding_dims: int
    created_at: datetime


class KnowledgeIngestionJob(BaseModel):
    job_id: str
    tenant_id: str
    team_id: str
    document_id: str
    source_uri: str
    status: str
    embedding_endpoint: str
    embedding_model: str
    total_chunks: int
    processed_chunks: int
    created_by: str
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class KnowledgeIngestResponse(BaseModel):
    job: KnowledgeIngestionJob
    chunks: list[KnowledgeChunk]


class KnowledgeRetrievalRequest(BaseModel):
    tenant_id: str
    team_id: str
    query: str
    role: str
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeRetrievalHit(BaseModel):
    chunk_id: str
    document_id: str
    tenant_id: str
    team_id: str
    source_type: str
    content: str
    distance: float


class KnowledgeRetrievalResponse(BaseModel):
    tenant_id: str
    team_id: str
    role: str
    hits: list[KnowledgeRetrievalHit]


@dataclass
class KnowledgeRepository:
    documents: dict[str, KnowledgeDocument] = field(default_factory=dict)
    jobs: dict[str, KnowledgeIngestionJob] = field(default_factory=dict)
    chunks: dict[str, KnowledgeChunk] = field(default_factory=dict)
    pending_ingestions: dict[str, tuple[str, KnowledgeIngestRequest]] = field(default_factory=dict)

    def create_document(self, payload: KnowledgeDocumentCreate) -> KnowledgeDocument:
        now = datetime.now(tz=UTC)
        document = KnowledgeDocument(
            document_id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            team_id=payload.team_id,
            repo_id=payload.repo_id,
            title=payload.title,
            source_type=payload.source_type,
            source_uri=payload.source_uri,
            source_version=payload.source_version,
            content_sha256=payload.content_sha256,
            metadata=payload.metadata,
            active=True,
            created_by=payload.created_by,
            created_at=now,
            updated_at=now,
        )
        self.documents[document.document_id] = document
        return document

    def list_documents(self, *, tenant_id: str, team_id: str) -> list[KnowledgeDocument]:
        return [
            document
            for document in self.documents.values()
            if document.tenant_id == tenant_id and document.team_id == team_id
        ]

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        return self.documents.get(document_id)

    def update_document(self, document_id: str, payload: KnowledgeDocumentUpdate) -> KnowledgeDocument | None:
        document = self.documents.get(document_id)
        if document is None:
            return None
        updated = document.model_copy(
            update={
                key: value
                for key, value in {
                    "title": payload.title,
                    "source_version": payload.source_version,
                    "active": payload.active,
                    "metadata": payload.metadata,
                    "updated_at": datetime.now(tz=UTC),
                }.items()
                if value is not None
            }
        )
        self.documents[document_id] = updated
        return updated

    def delete_document(self, document_id: str) -> bool:
        if document_id not in self.documents:
            return False
        del self.documents[document_id]
        for chunk_id, chunk in list(self.chunks.items()):
            if chunk.document_id == document_id:
                del self.chunks[chunk_id]
        return True

    def save_ingestion(self, job: KnowledgeIngestionJob, chunks: list[KnowledgeChunk]) -> None:
        self.jobs[job.job_id] = job
        self.pending_ingestions.pop(job.job_id, None)
        for chunk_id, chunk in list(self.chunks.items()):
            if chunk.document_id == job.document_id:
                del self.chunks[chunk_id]
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk

    def get_job(self, job_id: str) -> KnowledgeIngestionJob | None:
        return self.jobs.get(job_id)

    def search_chunks(
        self,
        *,
        tenant_id: str,
        team_id: str,
        query: str,
        limit: int,
    ) -> list[KnowledgeRetrievalHit]:
        query_terms = {term.casefold() for term in query.split() if term.strip()}
        hits: list[KnowledgeRetrievalHit] = []
        for chunk in self.chunks.values():
            if chunk.tenant_id != tenant_id or chunk.team_id != team_id:
                continue
            score = _lexical_score(query_terms, chunk.content)
            if score <= 0:
                continue
            hits.append(
                KnowledgeRetrievalHit(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    tenant_id=chunk.tenant_id,
                    team_id=chunk.team_id,
                    source_type=chunk.source_type,
                    content=chunk.content,
                    distance=1.0 - score,
                )
            )
        return sorted(hits, key=lambda hit: hit.distance)[:limit]

    def save_pending_ingestion(
        self,
        *,
        job: KnowledgeIngestionJob,
        document_id: str,
        request: KnowledgeIngestRequest,
    ) -> None:
        self.jobs[job.job_id] = job
        self.pending_ingestions[job.job_id] = (document_id, request)

    def get_pending_ingestion(self, job_id: str) -> tuple[KnowledgeDocument, KnowledgeIngestRequest] | None:
        pending = self.pending_ingestions.get(job_id)
        if pending is None:
            return None
        document_id, request = pending
        document = self.documents.get(document_id)
        if document is None:
            return None
        return document, request


class EmbeddingClient:
    def __init__(self, settings: InternalRagSettings) -> None:
        self.endpoint = settings.embedding_endpoint
        self.default_model = settings.embedding_model
        self.embedding_dims = 1536

    def embed(self, text: str, *, model: str) -> list[float]:
        digest = hashlib.sha256(f"{model}:{text}".encode()).digest()
        return [byte / 255 for byte in digest[:16]]


class KnowledgeIngestionService:
    def __init__(
        self,
        *,
        repository: KnowledgeRepository,
        embeddings: EmbeddingClient,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self.repository = repository
        self.embeddings = embeddings
        self.telemetry = telemetry

    def ingest(self, document: KnowledgeDocument, request: KnowledgeIngestRequest) -> KnowledgeIngestResponse:
        job = self.enqueue(document, request)
        processed = self.process_job(job.job_id)
        chunks = [
            chunk
            for chunk in self.repository.chunks.values()
            if chunk.document_id == document.document_id
        ]
        return KnowledgeIngestResponse(job=processed, chunks=chunks)

    def enqueue(self, document: KnowledgeDocument, request: KnowledgeIngestRequest) -> KnowledgeIngestionJob:
        model = request.embedding_model or self.embeddings.default_model
        job = KnowledgeIngestionJob(
            job_id=str(uuid.uuid4()),
            tenant_id=request.tenant_id,
            team_id=request.team_id,
            document_id=document.document_id,
            source_uri=document.source_uri,
            status="queued",
            embedding_endpoint=self.embeddings.endpoint,
            embedding_model=model,
            total_chunks=0,
            processed_chunks=0,
            created_by=document.created_by,
            created_at=datetime.now(tz=UTC),
        )
        self.repository.save_pending_ingestion(job=job, document_id=document.document_id, request=request)
        self._record_progress(job)
        return job

    def process_job(self, job_id: str) -> KnowledgeIngestionJob:
        existing = self.repository.get_job(job_id)
        if existing is None:
            raise KeyError(f"Knowledge ingestion job `{job_id}` was not found.")
        if existing.status == "completed":
            self._record_progress(existing, count_terminal=False)
            return existing

        pending = self.repository.get_pending_ingestion(job_id)
        if pending is None:
            failed = existing.model_copy(update={"status": "failed", "error_message": "pending_ingestion_missing"})
            self.repository.jobs[job_id] = failed
            self._record_progress(failed)
            return failed

        document, request = pending
        model = request.embedding_model or self.embeddings.default_model
        chunks = [
            self._build_chunk(document, text=chunk_text, chunk_index=index, model=model)
            for index, chunk_text in enumerate(_chunk_text(request.content, request.chunk_size))
        ]
        now = datetime.now(tz=UTC)
        running = existing.model_copy(
            update={
                "status": "running",
                "total_chunks": len(chunks),
                "processed_chunks": 0,
            }
        )
        self.repository.jobs[job_id] = running
        self._record_progress(running)
        completed = running.model_copy(
            update={
                "status": "completed",
                "processed_chunks": len(chunks),
                "completed_at": now,
            }
        )
        self.repository.save_ingestion(completed, chunks)
        self._record_progress(completed, count_terminal=True)
        return completed

    def _record_progress(self, job: KnowledgeIngestionJob, *, count_terminal: bool = False) -> None:
        if self.telemetry is None:
            return
        total = max(job.total_chunks, 1)
        self.telemetry.set_gauge(
            "devsquad_knowledge_ingestion_progress_ratio",
            job.processed_chunks / total,
            tenant_id=job.tenant_id,
            team_id=job.team_id,
            job_id=job.job_id,
            status=job.status,
        )
        self.telemetry.set_gauge(
            "devsquad_knowledge_ingestion_processed_chunks",
            float(job.processed_chunks),
            tenant_id=job.tenant_id,
            team_id=job.team_id,
            job_id=job.job_id,
        )
        if count_terminal and job.status == "completed":
            self.telemetry.increment(
                "devsquad_knowledge_ingestion_jobs_total",
                tenant_id=job.tenant_id,
                team_id=job.team_id,
                status=job.status,
            )

    def _build_chunk(
        self,
        document: KnowledgeDocument,
        *,
        text: str,
        chunk_index: int,
        model: str,
    ) -> KnowledgeChunk:
        self.embeddings.embed(text, model=model)
        return KnowledgeChunk(
            chunk_id=str(uuid.uuid4()),
            tenant_id=document.tenant_id,
            team_id=document.team_id,
            document_id=document.document_id,
            chunk_index=chunk_index,
            source_type=document.source_type,
            content=text,
            content_sha256=hashlib.sha256(text.encode()).hexdigest(),
            embedding_model=model,
            embedding_dims=self.embeddings.embedding_dims,
            created_at=datetime.now(tz=UTC),
            )


class KnowledgeRetrievalService:
    ROLE_WHITELIST = {"planner", "reviewer"}

    def __init__(
        self,
        *,
        repository: KnowledgeRepository,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self.repository = repository
        self.telemetry = telemetry

    def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResponse:
        started = perf_counter()
        if request.role not in self.ROLE_WHITELIST:
            raise PermissionError(f"knowledge_retrieval_denied:{request.role}")
        hits = self.repository.search_chunks(
            tenant_id=request.tenant_id,
            team_id=request.team_id,
            query=request.query,
            limit=request.limit,
        )
        response = KnowledgeRetrievalResponse(
            tenant_id=request.tenant_id,
            team_id=request.team_id,
            role=request.role,
            hits=hits,
        )
        self._record_retrieval_metrics(request, response, perf_counter() - started)
        return response

    def _record_retrieval_metrics(
        self,
        request: KnowledgeRetrievalRequest,
        response: KnowledgeRetrievalResponse,
        latency_seconds: float,
    ) -> None:
        if self.telemetry is None:
            return
        labels = {
            "tenant_id": request.tenant_id,
            "team_id": request.team_id,
            "role": request.role,
        }
        self.telemetry.observe("devsquad_knowledge_retrieval_latency_seconds", latency_seconds, **labels)
        self.telemetry.increment("devsquad_knowledge_retrieval_requests_total", **labels)
        if response.hits:
            self.telemetry.increment("devsquad_knowledge_retrieval_hits_total", **labels)
        self.telemetry.set_gauge(
            "devsquad_knowledge_retrieval_hit_ratio",
            1.0 if response.hits else 0.0,
            **labels,
        )
        for hit in response.hits:
            self.telemetry.observe(
                "devsquad_knowledge_excerpt_size_chars",
                float(len(hit.content)),
                **labels,
            )


def _chunk_text(content: str, chunk_size: int) -> list[str]:
    normalized = content.strip()
    if not normalized:
        return []
    return [
        normalized[index : index + chunk_size]
        for index in range(0, len(normalized), chunk_size)
    ]


def _lexical_score(query_terms: set[str], content: str) -> float:
    if not query_terms:
        return 0.0
    content_terms = {term.casefold().strip(".,:;!?()[]{}") for term in content.split()}
    if not content_terms:
        return 0.0
    overlap = len(query_terms & content_terms)
    return min(overlap / len(query_terms), 1.0)
