from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Engine, create_engine, delete, select, update

from backend.persistence.schema import (
    dpa_acknowledgements,
    dpa_versions,
    retention_policies,
    retention_runs,
    tenant_delete_events,
)
from backend.persistence.telemetry import bootstrap_telemetry

logger = logging.getLogger(__name__)


class RetentionPolicyCreate(BaseModel):
    surface: str
    tenant_id: str
    retention_days: int


class TenantDeleteRequest(BaseModel):
    tenant_id: str
    reason: str


class TenantDeleteApproval(BaseModel):
    event_id: str
    approver: str


class DpaPublication(BaseModel):
    version: str
    summary: str
    content: str
    published_by: str
    grace_period_days: int = 30


class DpaAcknowledgement(BaseModel):
    tenant_id: str
    dpa_version: str
    acknowledged_by: str


def _get_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True, pool_pre_ping=True)


def build_data_retention_router(database_url: str) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/data-retention", tags=["data-retention"])
    telemetry = bootstrap_telemetry()

    @router.get("/policies")
    def list_retention_policies(
        tenant_id: str | None = None,
        surface: str | None = None,
    ) -> list[dict]:
        engine = _get_engine(database_url)
        with engine.begin() as connection:
            stmt = select(retention_policies)
            if tenant_id:
                stmt = stmt.where(retention_policies.c.tenant_id == tenant_id)
            if surface:
                stmt = stmt.where(retention_policies.c.surface == surface)
            rows = connection.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    @router.post("/policies", status_code=status.HTTP_201_CREATED)
    def create_retention_policy(policy: RetentionPolicyCreate) -> dict:
        import uuid

        engine = _get_engine(database_url)
        policy_id = str(uuid.uuid4())
        with engine.begin() as connection:
            connection.execute(
                retention_policies.insert().values(
                    policy_id=policy_id,
                    surface=policy.surface,
                    tenant_id=policy.tenant_id,
                    retention_days=policy.retention_days,
                    enabled=True,
                )
            )
        return {
            "policy_id": policy_id,
            "surface": policy.surface,
            "retention_days": policy.retention_days,
        }

    @router.post("/run")
    def execute_retention_run(
        surface: str,
        tenant_id: str,
        mode: str = Query("dry_run", regex="^(dry_run|enforce)$"),
    ) -> dict:

        from datetime import datetime

        engine = _get_engine(database_url)
        run_id = str(uuid4())
        started_at = datetime.now(tz=UTC)

        policy = _get_policy(engine, surface, tenant_id)
        if policy is None:
            return {
                "run_id": run_id,
                "surface": surface,
                "tenant_id": tenant_id,
                "mode": mode,
                "rows_affected": 0,
                "status": "no_policy",
            }

        retention_days = policy["retention_days"]
        cutoff = started_at - timedelta(days=retention_days)

        rows_affected = 0
        try:
            if surface == "metering":
                rows_affected = _run_metering_retention(engine, cutoff, mode)
            elif surface == "dlq":
                rows_affected = _run_dlq_retention(engine, cutoff, mode)
            elif surface == "audit":
                rows_affected = _run_audit_retention(engine, cutoff, mode)
            else:
                rows_affected = 0

            duration_ms = int((datetime.now(tz=UTC) - started_at).total_seconds() * 1000)

            with engine.begin() as connection:
                connection.execute(
                    retention_runs.insert().values(
                        run_id=run_id,
                        surface=surface,
                        tenant_id=tenant_id,
                        rows_affected=rows_affected,
                        duration_ms=duration_ms,
                        status="success",
                        mode=mode,
                        started_at=started_at,
                        completed_at=datetime.now(tz=UTC),
                    )
                )

            telemetry.increment(
                "devsquad_retention_runs_total",
                surface=surface,
                tenant_id=tenant_id,
                mode=mode,
            )
            telemetry.set_gauge(
                "devsquad_retention_rows_deleted",
                float(rows_affected),
                surface=surface,
                tenant_id=tenant_id,
            )

            return {
                "run_id": run_id,
                "surface": surface,
                "tenant_id": tenant_id,
                "mode": mode,
                "rows_affected": rows_affected,
                "status": "success",
                "duration_ms": duration_ms,
            }

        except Exception as exc:
            duration_ms = int((datetime.now(tz=UTC) - started_at).total_seconds() * 1000)
            with engine.begin() as connection:
                connection.execute(
                    retention_runs.insert().values(
                        run_id=run_id,
                        surface=surface,
                        tenant_id=tenant_id,
                        rows_affected=0,
                        duration_ms=duration_ms,
                        status="failed",
                        error_message=str(exc),
                        mode=mode,
                        started_at=started_at,
                        completed_at=datetime.now(tz=UTC),
                    )
                )

            telemetry.increment(
                "devsquad_retention_run_failures_total",
                surface=surface,
                tenant_id=tenant_id,
            )

            raise HTTPException(status_code=500, detail=f"retention_run_failed:{exc}") from exc

    @router.get("/runs")
    def list_retention_runs(
        surface: str | None = None,
        tenant_id: str | None = None,
        limit: int = Query(50, le=200),
    ) -> list[dict]:
        engine = _get_engine(database_url)
        with engine.begin() as connection:
            stmt = select(retention_runs).order_by(retention_runs.c.started_at.desc()).limit(limit)
            if surface:
                stmt = stmt.where(retention_runs.c.surface == surface)
            if tenant_id:
                stmt = stmt.where(retention_runs.c.tenant_id == tenant_id)
            rows = connection.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    @router.post("/tenant-delete/request", status_code=status.HTTP_201_CREATED)
    def request_tenant_delete(
        request: TenantDeleteRequest,
        x_actor: Annotated[str, Header(alias="X-Actor")],
    ) -> dict:
        import uuid

        event_id = str(uuid.uuid4())
        engine = _get_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                tenant_delete_events.insert().values(
                    event_id=event_id,
                    tenant_id=request.tenant_id,
                    requested_by=x_actor,
                    reason=request.reason,
                    status="pending",
                )
            )

        logger.info(
            "tenant_delete_requested",
            extra={
                "event_id": event_id,
                "tenant_id": request.tenant_id,
                "requested_by": x_actor,
            },
        )

        return {
            "event_id": event_id,
            "tenant_id": request.tenant_id,
            "status": "pending",
        }

    @router.post("/tenant-delete/approve")
    def approve_tenant_delete(
        approval: TenantDeleteApproval,
        x_actor: Annotated[str, Header(alias="X-Actor")],
    ) -> dict:
        from datetime import datetime

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            row = connection.execute(
                select(tenant_delete_events).where(tenant_delete_events.c.event_id == approval.event_id)
            ).mappings().first()

            if row is None:
                raise HTTPException(status_code=404, detail="delete_event_not_found")

            if row["status"] == "completed":
                raise HTTPException(status_code=400, detail="delete_already_completed")

            if row["approved_by_first"] is None:
                first_approver = x_actor
                second_approver = None
                approved_at = None
                new_status = "pending_second_approval"
            elif row["approved_by_first"] == x_actor:
                raise HTTPException(status_code=400, detail="same_approver_cannot_approve_twice")
            else:
                first_approver = row["approved_by_first"]
                second_approver = x_actor
                approved_at = datetime.now(tz=UTC)
                new_status = "approved"

            connection.execute(
                update(tenant_delete_events)
                .where(tenant_delete_events.c.event_id == approval.event_id)
                .values(
                    approved_by_first=first_approver,
                    approved_by_second=second_approver,
                    approved_at=approved_at,
                    status=new_status,
                )
            )

        return {
            "event_id": approval.event_id,
            "status": new_status,
            "approved_by_first": first_approver,
            "approved_by_second": second_approver,
        }

    @router.post("/tenant-delete/{event_id}/execute")
    def execute_tenant_delete(
        event_id: str,
        x_actor: Annotated[str, Header(alias="X-Actor")],
    ) -> dict:
        from datetime import datetime

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            row = connection.execute(
                select(tenant_delete_events).where(tenant_delete_events.c.event_id == event_id)
            ).mappings().first()

            if row is None:
                raise HTTPException(status_code=404, detail="delete_event_not_found")

            if row["status"] != "approved":
                raise HTTPException(status_code=400, detail="delete_not_approved")

            tenant_id = row["tenant_id"]
            deletion_counts = _execute_cascade_delete(engine, tenant_id)

            pseudonymized_actor = hashlib.sha256(x_actor.encode()).hexdigest()[:16]

            connection.execute(
                update(tenant_delete_events)
                .where(tenant_delete_events.c.event_id == event_id)
                .values(
                    status="completed",
                    deletion_counts=deletion_counts,
                    completed_at=datetime.now(tz=UTC),
                )
            )

        logger.info(
            "tenant_delete_completed",
            extra={
                "event_id": event_id,
                "tenant_id": tenant_id,
                "deletion_counts": deletion_counts,
                "executed_by": pseudonymized_actor,
            },
        )

        telemetry.increment(
            "devsquad_tenant_deletions_total",
            tenant_id=tenant_id,
        )

        return {
            "event_id": event_id,
            "tenant_id": tenant_id,
            "status": "completed",
            "deletion_counts": deletion_counts,
        }

    @router.get("/tenant-delete")
    def list_tenant_delete_events(
        tenant_id: str | None = None,
        status_filter: str | None = None,
    ) -> list[dict]:
        engine = _get_engine(database_url)
        with engine.begin() as connection:
            stmt = select(tenant_delete_events).order_by(tenant_delete_events.c.created_at.desc())
            if tenant_id:
                stmt = stmt.where(tenant_delete_events.c.tenant_id == tenant_id)
            if status_filter:
                stmt = stmt.where(tenant_delete_events.c.status == status_filter)
            rows = connection.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    @router.post("/dpa/publish", status_code=status.HTTP_201_CREATED)
    def publish_dpa_version(
        publication: DpaPublication,
    ) -> dict:
        import hashlib
        from datetime import datetime

        content_hash = hashlib.sha256(publication.content.encode()).hexdigest()
        engine = _get_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                dpa_versions.insert().values(
                    version=publication.version,
                    published_at=datetime.now(tz=UTC),
                    content_hash=content_hash,
                    summary=publication.summary,
                    published_by=publication.published_by,
                    grace_period_days=publication.grace_period_days,
                )
            )

        return {
            "version": publication.version,
            "content_hash": content_hash,
            "grace_period_days": publication.grace_period_days,
        }

    @router.post("/dpa/acknowledge", status_code=status.HTTP_201_CREATED)
    def acknowledge_dpa(
        ack: DpaAcknowledgement,
    ) -> dict:
        import uuid

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            version_row = connection.execute(
                select(dpa_versions).where(dpa_versions.c.version == ack.dpa_version)
            ).mappings().first()

            if version_row is None:
                raise HTTPException(status_code=404, detail="dpa_version_not_found")

            ack_id = str(uuid.uuid4())
            connection.execute(
                dpa_acknowledgements.insert().values(
                    ack_id=ack_id,
                    tenant_id=ack.tenant_id,
                    dpa_version=ack.dpa_version,
                    acknowledged_by=ack.acknowledged_by,
                )
            )

        return {
            "ack_id": ack_id,
            "tenant_id": ack.tenant_id,
            "dpa_version": ack.dpa_version,
        }

    @router.get("/dpa/status")
    def get_dpa_status(
        tenant_id: str,
    ) -> dict:
        from datetime import datetime

        engine = _get_engine(database_url)
        with engine.begin() as connection:
            latest_version = connection.execute(
                select(dpa_versions).order_by(dpa_versions.c.published_at.desc()).limit(1)
            ).mappings().first()

            if latest_version is None:
                return {"tenant_id": tenant_id, "dpa_required": False, "status": "no_dpa_published"}

            ack = connection.execute(
                select(dpa_acknowledgements)
                .where(dpa_acknowledgements.c.tenant_id == tenant_id)
                .where(dpa_acknowledgements.c.dpa_version == latest_version["version"])
            ).mappings().first()

            grace_expired = False
            if ack is None:
                grace_cutoff = latest_version["published_at"] + timedelta(
                    days=latest_version["grace_period_days"]
                )
                grace_expired = datetime.now(tz=UTC) > grace_cutoff

            return {
                "tenant_id": tenant_id,
                "current_dpa_version": latest_version["version"],
                "acknowledged": ack is not None,
                "grace_period_expired": grace_expired,
                "processing_blocked": grace_expired and ack is None,
            }

    @router.get("/dpa")
    def list_dpa_versions() -> list[dict]:
        engine = _get_engine(database_url)
        with engine.begin() as connection:
            rows = connection.execute(
                select(dpa_versions).order_by(dpa_versions.c.published_at.desc())
            ).mappings().all()
        return [dict(row) for row in rows]

    return router


def _get_policy(engine: Engine, surface: str, tenant_id: str) -> dict | None:
    with engine.begin() as connection:
        row = connection.execute(
            select(retention_policies)
            .where(retention_policies.c.surface == surface)
            .where(retention_policies.c.tenant_id == tenant_id)
            .where(retention_policies.c.enabled.is_(True))
        ).mappings().first()
    return dict(row) if row else None


def _run_metering_retention(engine: Engine, cutoff: datetime, mode: str) -> int:
    from backend.persistence.schema import metering_facts

    with engine.begin() as connection:
        if mode == "enforce":
            result = connection.execute(
                delete(metering_facts).where(metering_facts.c.completed_at < cutoff)
            )
            return result.rowcount
        else:
            from sqlalchemy import func

            result = connection.execute(
                select(func.count()).select_from(metering_facts).where(metering_facts.c.completed_at < cutoff)
            )
            return result.scalar() or 0


def _run_dlq_retention(engine: Engine, cutoff: datetime, mode: str) -> int:
    from backend.persistence.schema import dead_letter_records

    with engine.begin() as connection:
        if mode == "enforce":
            result = connection.execute(
                delete(dead_letter_records).where(dead_letter_records.c.created_at < cutoff)
            )
            return result.rowcount
        else:
            from sqlalchemy import func

            result = connection.execute(
                select(func.count()).select_from(dead_letter_records).where(dead_letter_records.c.created_at < cutoff)
            )
            return result.scalar() or 0


def _run_audit_retention(engine: Engine, cutoff: datetime, mode: str) -> int:
    from backend.persistence.schema import audit_events

    with engine.begin() as connection:
        if mode == "enforce":
            result = connection.execute(
                delete(audit_events).where(audit_events.c.created_at < cutoff)
            )
            return result.rowcount
        else:
            from sqlalchemy import func

            result = connection.execute(
                select(func.count()).select_from(audit_events).where(audit_events.c.created_at < cutoff)
            )
            return result.scalar() or 0


def _execute_cascade_delete(engine: Engine, tenant_id: str) -> dict:
    from backend.persistence.schema import (
        budget_cap_snapshots,
        budget_charges,
        budget_denials,
        budget_reservations,
        dead_letter_records,
        metering_facts,
        metering_hourly_rollups,
        runs,
    )

    counts: dict[str, int] = {}
    tables = [
        ("budget_denials", budget_denials),
        ("budget_charges", budget_charges),
        ("budget_reservations", budget_reservations),
        ("budget_cap_snapshots", budget_cap_snapshots),
        ("metering_hourly_rollups", metering_hourly_rollups),
        ("metering_facts", metering_facts),
        ("dead_letter_records", dead_letter_records),
        ("runs", runs),
    ]

    with engine.begin() as connection:
        for name, table in tables:
            result = connection.execute(
                delete(table).where(table.c.tenant_id == tenant_id)
            )
            counts[name] = result.rowcount

    return counts
