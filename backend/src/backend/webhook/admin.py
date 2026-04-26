from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel

from backend.persistence.webhook import SqlAlchemyWebhookIdempotencyStore

logger = logging.getLogger(__name__)


class SecretRotationRequest(BaseModel):
    tenant_id: str
    team_id: str
    new_secret: str
    overlap_hours: int = 24


class SecretRotationResponse(BaseModel):
    rotation_id: str
    tenant_id: str
    team_id: str
    rotation_overlap_until: str | None
    rotated_by: str


class AllowlistUpdateRequest(BaseModel):
    tenant_id: str
    team_id: str
    cidrs: list[str]


class AllowlistResponse(BaseModel):
    tenant_id: str
    team_id: str
    cidrs: list[str]


def build_webhook_admin_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/webhook", tags=["webhook-admin"])

    @router.post("/rotate-secret", status_code=status.HTTP_201_CREATED)
    def rotate_secret(
        request: SecretRotationRequest,
        x_actor: Annotated[str, Header(alias="X-Actor")],
    ) -> SecretRotationResponse:
        from backend.persistence.factory import build_persistence_adapters

        adapters = build_persistence_adapters()
        database_url = adapters.database.settings.sync_url()
        store = SqlAlchemyWebhookIdempotencyStore(database_url)

        rotation_id = str(uuid4())
        overlap_until = datetime.now(tz=UTC) + timedelta(hours=request.overlap_hours)
        previous_secret_hash = hashlib.sha256(request.new_secret.encode()).hexdigest()[:16]

        store.record_rotation(
            tenant_id=request.tenant_id,
            team_id=request.team_id,
            rotation_id=rotation_id,
            previous_secret_hash=previous_secret_hash,
            rotation_overlap_until=overlap_until,
            rotated_by=x_actor,
            metadata={"overlap_hours": request.overlap_hours},
        )

        logger.info(
            "webhook_credential_rotated",
            extra={
                "tenant_id": request.tenant_id,
                "team_id": request.team_id,
                "rotation_id": rotation_id,
                "rotated_by": x_actor,
            },
        )

        return SecretRotationResponse(
            rotation_id=rotation_id,
            tenant_id=request.tenant_id,
            team_id=request.team_id,
            rotation_overlap_until=overlap_until.isoformat(),
            rotated_by=x_actor,
        )

    @router.get("/secret-rotation-status")
    def get_rotation_status(
        tenant_id: str,
        team_id: str,
    ) -> dict:
        from backend.persistence.factory import build_persistence_adapters

        adapters = build_persistence_adapters()
        database_url = adapters.database.settings.sync_url()
        store = SqlAlchemyWebhookIdempotencyStore(database_url)

        rotation = store.get_latest_rotation(tenant_id, team_id)
        if rotation is None:
            return {"tenant_id": tenant_id, "team_id": team_id, "status": "no_rotations"}

        overlap_active = False
        if rotation.get("rotation_overlap_until"):
            overlap_active = datetime.now(tz=UTC) <= rotation["rotation_overlap_until"]

        return {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "rotation_id": rotation["rotation_id"],
            "rotated_by": rotation["rotated_by"],
            "rotation_overlap_until": rotation.get("rotation_overlap_until"),
            "overlap_active": overlap_active,
            "created_at": rotation["created_at"],
        }

    @router.put("/ip-allowlist")
    def update_ip_allowlist(
        request: AllowlistUpdateRequest,
        x_actor: Annotated[str, Header(alias="X-Actor")],
    ) -> AllowlistResponse:
        import ipaddress

        for cidr in request.cidrs:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"invalid_cidr:{cidr}:{exc}",
                ) from exc

        logger.info(
            "webhook_ip_allowlist_updated",
            extra={
                "tenant_id": request.tenant_id,
                "team_id": request.team_id,
                "cidr_count": len(request.cidrs),
                "updated_by": x_actor,
            },
        )

        return AllowlistResponse(
            tenant_id=request.tenant_id,
            team_id=request.team_id,
            cidrs=request.cidrs,
        )

    @router.get("/ip-allowlist")
    def get_ip_allowlist(
        tenant_id: str,
        team_id: str,
    ) -> AllowlistResponse:
        return AllowlistResponse(
            tenant_id=tenant_id,
            team_id=team_id,
            cidrs=[],
        )

    @router.get("/rate-limit-rejections")
    def list_rate_limit_rejections(
        tenant_id: str,
        ticket_key: str | None = None,
        limit: int = Query(50, le=200),
    ) -> list[dict]:
        from sqlalchemy import select as sa_select

        from backend.persistence.factory import build_persistence_adapters
        from backend.persistence.schema import webhook_rate_limit_rejections as rl_table
        from backend.persistence.webhook import SqlAlchemyWebhookIdempotencyStore as Store

        adapters = build_persistence_adapters()
        database_url = adapters.database.settings.sync_url()
        store = Store(database_url)

        with store._engine.begin() as connection:
            stmt = (
                sa_select(rl_table)
                .where(rl_table.c.tenant_id == tenant_id)
                .order_by(rl_table.c.rejected_at.desc())
                .limit(limit)
            )
            if ticket_key:
                stmt = stmt.where(rl_table.c.ticket_key == ticket_key)
            rows = connection.execute(stmt).mappings().all()

        return [dict(row) for row in rows]

    return router
