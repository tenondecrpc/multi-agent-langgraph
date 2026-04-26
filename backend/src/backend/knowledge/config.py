from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel
from sqlalchemy.engine import make_url

from backend.operations.release import FeatureFlagDefinition

INTERNAL_RAG_FEATURE_FLAG = FeatureFlagDefinition(
    flag_id="internal_rag_enabled",
    flag_type="release",
    default_enabled=False,
    auditable=True,
)


class InternalRagSettings(BaseModel):
    enabled: bool = False
    database_url: str | None = None
    embedding_endpoint: str = "http://embedding-service.dev-squad.svc.cluster.local/embed"
    embedding_model: str = "self-hosted-embedding-v1"

    @classmethod
    def from_env(cls) -> InternalRagSettings:
        raw_enabled = os.getenv("INTERNAL_RAG_ENABLED", "false").strip().lower()
        return cls(
            enabled=raw_enabled in {"1", "true", "yes", "on"},
            database_url=os.getenv("DATABASE_URL") or os.getenv("BACKEND_DATABASE_URL"),
            embedding_endpoint=os.getenv(
                "INTERNAL_RAG_EMBEDDING_ENDPOINT",
                "http://embedding-service.dev-squad.svc.cluster.local/embed",
            ),
            embedding_model=os.getenv("INTERNAL_RAG_EMBEDDING_MODEL", "self-hosted-embedding-v1"),
        )


class InternalRagProbeResult(BaseModel):
    enabled: bool
    ready: bool
    reason: str | None = None


async def probe_pgvector_extension(settings: InternalRagSettings) -> InternalRagProbeResult:
    if not settings.enabled:
        return InternalRagProbeResult(enabled=False, ready=True)

    if not settings.database_url:
        return InternalRagProbeResult(
            enabled=True,
            ready=False,
            reason="internal_rag_database_url_missing",
        )

    try:
        import asyncpg

        connection = await asyncpg.connect(**_asyncpg_connect_kwargs(settings.database_url))
        try:
            installed = await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            )
        finally:
            await connection.close()
    except Exception:
        return InternalRagProbeResult(
            enabled=True,
            ready=False,
            reason="internal_rag_pgvector_probe_failed",
        )

    if not installed:
        return InternalRagProbeResult(
            enabled=True,
            ready=False,
            reason="internal_rag_pgvector_missing",
        )

    return InternalRagProbeResult(enabled=True, ready=True)


def _asyncpg_connect_kwargs(database_url: str) -> dict[str, Any]:
    parsed = make_url(database_url)
    kwargs: dict[str, Any] = {
        "database": parsed.database or "postgres",
        "user": parsed.username or "postgres",
    }
    if parsed.password:
        kwargs["password"] = parsed.password
    host = parsed.query.get("host") or parsed.host
    if host:
        kwargs["host"] = host
    if parsed.port:
        kwargs["port"] = parsed.port
    elif "port" in parsed.query:
        kwargs["port"] = int(parsed.query["port"])
    return kwargs
