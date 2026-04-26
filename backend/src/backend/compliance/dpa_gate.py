from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class DpaGateMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        database_url: str,
        excluded_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._database_url = database_url
        self._excluded_paths = excluded_paths or [
            "/healthz",
            "/readyz",
            "/metrics",
            "/api/v1/status-page",
            "/api/v1/admin/data-retention/dpa/status",
            "/api/v1/admin/data-retention/dpa/acknowledge",
            "/api/v1/admin/data-retention/dpa",
            "/api/v1/admin/data-retention/dpa/publish",
        ]

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._is_excluded(request.url.path):
            return await call_next(request)

        if request.method == "POST" and "/webhooks" in request.url.path:
            tenant_id = await self._extract_tenant_id(request)
            if tenant_id and not self._is_dpa_acknowledged(tenant_id):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "dpa_not_acknowledged",
                        "message": "Ticket processing is blocked until the current DPA version is acknowledged.",
                        "tenant_id": tenant_id,
                    },
                )

        return await call_next(request)

    def _is_excluded(self, path: str) -> bool:
        return any(path.startswith(excluded) for excluded in self._excluded_paths)

    async def _extract_tenant_id(self, request: Request) -> str | None:
        try:
            body = await request.body()
            import json

            payload = json.loads(body)
            return payload.get("tenant_id")
        except Exception:
            return None

    def _is_dpa_acknowledged(self, tenant_id: str) -> bool:
        from sqlalchemy import create_engine, select

        from backend.persistence.schema import dpa_acknowledgements, dpa_versions

        engine = create_engine(self._database_url, future=True, pool_pre_ping=True)
        with engine.begin() as connection:
            latest_version = connection.execute(
                select(dpa_versions).order_by(dpa_versions.c.published_at.desc()).limit(1)
            ).mappings().first()

            if latest_version is None:
                return True

            ack = connection.execute(
                select(dpa_acknowledgements)
                .where(dpa_acknowledgements.c.tenant_id == tenant_id)
                .where(dpa_acknowledgements.c.dpa_version == latest_version["version"])
            ).mappings().first()

            if ack is not None:
                return True

            grace_cutoff = latest_version["published_at"] + timedelta(
                days=latest_version["grace_period_days"]
            )
            return datetime.now(tz=UTC) <= grace_cutoff
