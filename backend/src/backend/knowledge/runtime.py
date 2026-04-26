from __future__ import annotations

from backend.runtime.models import KnowledgeExcerptSummary, TicketRunState

from .service import KnowledgeRetrievalResponse


def persist_retrieval_summaries(
    run: TicketRunState,
    response: KnowledgeRetrievalResponse,
    *,
    max_excerpt_chars: int = 500,
) -> TicketRunState:
    for hit in response.hits:
        run.knowledge_excerpts.append(
            KnowledgeExcerptSummary(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                source_type=hit.source_type,
                distance=hit.distance,
                excerpt=hit.content[:max_excerpt_chars],
            )
        )
    return run
