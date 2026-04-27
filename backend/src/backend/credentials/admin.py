from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Engine, create_engine, select, update

from backend.persistence.schema import (
    break_glass_grants,
    credential_rotation_schedule,
    kek_versions,
)
from backend.persistence.telemetry import bootstrap_telemetry
from backend.security.auth import AuthContext, AuthRole, require_role

logger = logging.getLogger(__name__)


class CredentialRotationEntry(BaseModel):
    schedule_id: str
    tenant_id: str
    team_id: str
    credential_kind: str
    credential_id: str
    rotated_at: str
    next_rotation_due: str
    rotation_sla_days: int
    overdue: bool


class BreakGlassRequest(BaseModel):
    tenant_id: str
    team_id: str
    reason: str
    scope: dict = {}
    duration_hours: int = 4


class BreakGlassApproval(BaseModel):
    grant_id: str
    approver: str


class BreakGlassGrant(BaseModel):
    grant_id: str
    tenant_id: str
    team_id: str
    requested_by: str
    reason: str
    scope: dict
    approved_by_first: str | None
    approved_by_second: str | None
    granted_at: str | None
    expires_at: str
    revoked_at: str | None
    status: str


class KekIntroduction(BaseModel):
    kek_id: str
    kms_ref: str
    introduced_by: str
    metadata: dict = {}


class KekRotationRequest(BaseModel):
    new_kek_id: str
    kms_ref: str
    introduced_by: str
    metadata: dict = {}


def _get_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True, pool_pre_ping=True)


def build_credential_rotation_router(
    database_url: str,
    *,
    auth_policy: Depends | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/credentials", tags=["credential-rotation"])
    telemetry = bootstrap_telemetry()
    auth_dep = auth_policy or Depends(require_role(AuthRole.ADMIN))

    @router.get("/rotation-schedule")
    def list_rotation_schedule(
        tenant_id: str | None = None,
        overdue_only: bool = False,
        auth: AuthContext = auth_dep,
    ) -> list[dict]:
        engine = _get_engine(database_url)
        with engine.begin() as connection:
            stmt = select(credential_rotation_schedule).order_by(
                credential_rotation_schedule.c.next_rotation_due.asc()
            )
            if tenant_id:
                stmt = stmt.where(credential_rotation_schedule.c.tenant_id == tenant_id)
            if overdue_only:
                stmt = stmt.where(credential_rotation_schedule.c.overdue.is_(True))
            rows = connection.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    @router.post("/rotation-schedule", status_code=status.HTTP_201_CREATED)
    def upsert_rotation_schedule(
        tenant_id: str,
        team_id: str,
        credential_kind: str,
        credential_id: str,
        rotation_sla_days: int = 90,
        auth: AuthContext = auth_dep,
    ) -> dict:
        import uuid
        from datetime import UTC, datetime

        engine = _get_engine(database_url)
        schedule_id = str(uuid.uuid4())
        now = datetime.now(tz=UTC)
        next_due = now + timedelta(days=rotation_sla_days)

        with engine.begin() as connection:
            connection.execute(
                credential_rotation_schedule.insert().values(
                    schedule_id=schedule_id,
                    tenant_id=tenant_id,
                    team_id=team_id,
                    credential_kind=credential_kind,
                    credential_id=credential_id,
                    rotated_at=now,
                    next_rotation_due=next_due,
                    rotation_sla_days=rotation_sla_days,
                    overdue=False,
                )
            )

        telemetry.set_gauge(
            "devsquad_credential_rotation_overdue_count",
            _count_overdue(engine),
        )

        return {
            "schedule_id": schedule_id,
            "tenant_id": tenant_id,
            "credential_kind": credential_kind,
            "next_rotation_due": next_due.isoformat(),
        }

    @router.post("/rotation-schedule/evaluate")
    def evaluate_rotation_schedule(
        auth: AuthContext = auth_dep,
    ) -> dict:
        engine = _get_engine(database_url)
        now = datetime.now(tz=UTC)
        warning_count = 0
        overdue_count = 0

        with engine.begin() as connection:
            rows = connection.execute(
                select(credential_rotation_schedule)
            ).mappings().all()

            for row in rows:
                next_due = row["next_rotation_due"]
                if next_due.tzinfo is None:
                    next_due = next_due.replace(tzinfo=UTC)
                days_until_due = (next_due - now).days
                is_overdue = days_until_due < 0
                is_warning = 0 <= days_until_due <= 14

                if is_overdue or is_warning:
                    connection.execute(
                        update(credential_rotation_schedule)
                        .where(credential_rotation_schedule.c.schedule_id == row["schedule_id"])
                        .values(
                            overdue=is_overdue,
                            updated_at=now,
                        )
                    )
                    if is_overdue:
                        overdue_count += 1
                    else:
                        warning_count += 1

        telemetry.set_gauge(
            "devsquad_credential_rotation_overdue_count",
            float(overdue_count),
        )
        telemetry.set_gauge(
            "devsquad_credential_rotation_warning_count",
            float(warning_count),
        )

        if overdue_count > 0:
            telemetry.increment(
                "devsquad_credential_rotation_overdue_alerts_total",
                count=overdue_count,
            )

        return {
            "evaluated_at": now.isoformat(),
            "warning_count": warning_count,
            "overdue_count": overdue_count,
        }

    @router.get("/rotation-schedule/blocking-status")
    def check_blocking_status(
        tenant_id: str,
        team_id: str,
        auth: AuthContext = auth_dep,
    ) -> dict:
        engine = _get_engine(database_url)
        with engine.begin() as connection:
            rows = connection.execute(
                select(credential_rotation_schedule)
                .where(credential_rotation_schedule.c.tenant_id == tenant_id)
                .where(credential_rotation_schedule.c.team_id == team_id)
                .where(credential_rotation_schedule.c.overdue.is_(True))
            ).mappings().all()

        blocked = len(rows) > 0
        return {
            "tenant_id": tenant_id,
            "team_id": team_id,
            "blocked": blocked,
            "overdue_credentials": [
                {
                    "credential_kind": row["credential_kind"],
                    "credential_id": row["credential_id"],
                    "next_rotation_due": row["next_rotation_due"].isoformat(),
                }
                for row in rows
            ],
        }

    @router.post("/break-glass/request", status_code=status.HTTP_201_CREATED)
    def request_break_glass(
        request: BreakGlassRequest,
        x_actor: Annotated[str, Header(alias="X-Actor")],
        auth: AuthContext = auth_dep,
    ) -> dict:
        import uuid
        from datetime import UTC, datetime

        grant_id = str(uuid.uuid4())
        expires_at = datetime.now(tz=UTC) + timedelta(hours=request.duration_hours)

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                break_glass_grants.insert().values(
                    grant_id=grant_id,
                    tenant_id=request.tenant_id,
                    team_id=request.team_id,
                    requested_by=x_actor,
                    reason=request.reason,
                    scope=request.scope,
                    expires_at=expires_at,
                )
            )

        logger.info(
            "break_glass_requested",
            extra={
                "grant_id": grant_id,
                "tenant_id": request.tenant_id,
                "requested_by": x_actor,
            },
        )

        return {
            "grant_id": grant_id,
            "status": "pending_approval",
            "expires_at": expires_at.isoformat(),
        }

    @router.post("/break-glass/approve")
    def approve_break_glass(
        approval: BreakGlassApproval,
        x_actor: Annotated[str, Header(alias="X-Actor")],
        auth: AuthContext = auth_dep,
    ) -> dict:
        from datetime import UTC, datetime

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            row = connection.execute(
                select(break_glass_grants).where(break_glass_grants.c.grant_id == approval.grant_id)
            ).mappings().first()

            if row is None:
                raise HTTPException(status_code=404, detail="grant_not_found")

            if row["revoked_at"] is not None:
                raise HTTPException(status_code=400, detail="grant_revoked")

            if row["approved_by_first"] is None:
                first_approver = x_actor
                second_approver = None
                granted_at = None
                status_text = "pending_second_approval"
            elif row["approved_by_first"] == x_actor:
                raise HTTPException(status_code=400, detail="same_approver_cannot_approve_twice")
            else:
                first_approver = row["approved_by_first"]
                second_approver = x_actor
                granted_at = datetime.now(tz=UTC)
                status_text = "granted"

            connection.execute(
                update(break_glass_grants)
                .where(break_glass_grants.c.grant_id == approval.grant_id)
                .values(
                    approved_by_first=first_approver,
                    approved_by_second=second_approver,
                    granted_at=granted_at,
                )
            )

        telemetry.increment(
            "devsquad_break_glass_approvals_total",
            tenant_id=row["tenant_id"],
        )

        return {
            "grant_id": approval.grant_id,
            "status": status_text,
            "approved_by_first": first_approver,
            "approved_by_second": second_approver,
            "granted_at": granted_at.isoformat() if granted_at else None,
        }

    @router.post("/break-glass/{grant_id}/revoke")
    def revoke_break_glass(
        grant_id: str,
        reason: str,
        x_actor: Annotated[str, Header(alias="X-Actor")],
        auth: AuthContext = auth_dep,
    ) -> dict:
        from datetime import UTC, datetime

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            result = connection.execute(
                update(break_glass_grants)
                .where(break_glass_grants.c.grant_id == grant_id)
                .values(
                    revoked_at=datetime.now(tz=UTC),
                    revoked_by=x_actor,
                    revoke_reason=reason,
                )
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="grant_not_found")

        logger.info(
            "break_glass_revoked",
            extra={
                "grant_id": grant_id,
                "revoked_by": x_actor,
                "reason": reason,
            },
        )

        return {"grant_id": grant_id, "status": "revoked"}

    @router.get("/break-glass")
    def list_break_glass_grants(
        tenant_id: str | None = None,
        active_only: bool = False,
        auth: AuthContext = auth_dep,
    ) -> list[dict]:
        from datetime import UTC, datetime

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            stmt = select(break_glass_grants).order_by(
                break_glass_grants.c.created_at.desc()
            )
            if tenant_id:
                stmt = stmt.where(break_glass_grants.c.tenant_id == tenant_id)
            rows = connection.execute(stmt).mappings().all()

        results = []
        now = datetime.now(tz=UTC)
        for row in rows:
            granted = row["granted_at"] is not None and row["approved_by_second"] is not None
            expired = row["expires_at"] < now if row["expires_at"] else False
            revoked = row["revoked_at"] is not None

            if granted and not expired and not revoked:
                status_text = "active"
            elif revoked:
                status_text = "revoked"
            elif expired:
                status_text = "expired"
            elif granted:
                status_text = "pending_second_approval"
            else:
                status_text = "pending_first_approval"

            results.append({
                "grant_id": row["grant_id"],
                "tenant_id": row["tenant_id"],
                "team_id": row["team_id"],
                "requested_by": row["requested_by"],
                "reason": row["reason"],
                "scope": row["scope"],
                "approved_by_first": row["approved_by_first"],
                "approved_by_second": row["approved_by_second"],
                "granted_at": row["granted_at"].isoformat() if row["granted_at"] else None,
                "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None,
                "status": status_text,
            })

        if active_only:
            results = [r for r in results if r["status"] == "active"]

        return results

    @router.post("/kek/introduce", status_code=status.HTTP_201_CREATED)
    def introduce_kek(
        request: KekIntroduction,
        auth: AuthContext = auth_dep,
    ) -> dict:
        from datetime import UTC, datetime

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                kek_versions.insert().values(
                    kek_id=request.kek_id,
                    kms_ref=request.kms_ref,
                    introduced_at=datetime.now(tz=UTC),
                    is_default=False,
                    introduced_by=request.introduced_by,
                    metadata=request.metadata,
                )
            )

        return {
            "kek_id": request.kek_id,
            "status": "introduced",
            "is_default": False,
        }

    @router.post("/kek/rotate-default")
    def rotate_kek_default(
        new_kek_id: str,
        x_actor: Annotated[str, Header(alias="X-Actor")],
        auth: AuthContext = auth_dep,
    ) -> dict:

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            existing = connection.execute(
                select(kek_versions).where(kek_versions.c.kek_id == new_kek_id)
            ).mappings().first()

            if existing is None:
                raise HTTPException(status_code=404, detail="kek_not_found")

            connection.execute(
                update(kek_versions)
                .where(kek_versions.c.is_default.is_(True))
                .values(is_default=False)
            )
            connection.execute(
                update(kek_versions)
                .where(kek_versions.c.kek_id == new_kek_id)
                .values(is_default=True)
            )

        logger.info(
            "kek_default_rotated",
            extra={
                "new_kek_id": new_kek_id,
                "rotated_by": x_actor,
            },
        )

        return {
            "kek_id": new_kek_id,
            "status": "default",
        }

    @router.post("/kek/{kek_id}/retire")
    def retire_kek(
        kek_id: str,
        x_actor: Annotated[str, Header(alias="X-Actor")],
        auth: AuthContext = auth_dep,
    ) -> dict:
        from datetime import UTC, datetime

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            result = connection.execute(
                update(kek_versions)
                .where(kek_versions.c.kek_id == kek_id)
                .where(kek_versions.c.is_default.is_(False))
                .values(retired_at=datetime.now(tz=UTC))
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=400, detail="cannot_retire_default_or_missing_kek")

        return {"kek_id": kek_id, "status": "retired"}

    @router.get("/kek")
    def list_kek_versions() -> list[dict]:
        engine = _get_engine(database_url)
        with engine.begin() as connection:
            rows = connection.execute(
                select(kek_versions).order_by(kek_versions.c.introduced_at.desc())
            ).mappings().all()
        return [dict(row) for row in rows]

    return router


def _count_overdue(engine: Engine) -> float:
    with engine.begin() as connection:
        result = connection.execute(
            select(credential_rotation_schedule)
            .where(credential_rotation_schedule.c.overdue.is_(True))
        )
        return float(len(result.fetchall()))
