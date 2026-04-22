from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .migrations import MigrationStatus


class AdapterReadiness(BaseModel):
    name: str
    configured: bool
    healthy: bool


class ProbeResult(BaseModel):
    status: Literal["ok", "degraded", "not_ready"]
    reasons: list[str]


class PersistenceHealthSnapshot(BaseModel):
    database: AdapterReadiness
    redis: AdapterReadiness
    encryption: AdapterReadiness
    migration: MigrationStatus | None = None
    active_snapshot_id: str | None = None
    migration_revision: str | None = None


class PersistenceHealthService:
    def __init__(
        self,
        *,
        database_ready: bool = False,
        redis_ready: bool = False,
        encryption_ready: bool = False,
        migration_status: MigrationStatus | None = None,
        active_snapshot_id: str | None = None,
    ) -> None:
        self.database_ready = database_ready
        self.redis_ready = redis_ready
        self.encryption_ready = encryption_ready
        self.migration_status = migration_status
        self.active_snapshot_id = active_snapshot_id

    def snapshot(self) -> PersistenceHealthSnapshot:
        return PersistenceHealthSnapshot(
            database=AdapterReadiness(
                name="database",
                configured=self.database_ready,
                healthy=self.database_ready,
            ),
            redis=AdapterReadiness(
                name="redis",
                configured=self.redis_ready,
                healthy=self.redis_ready,
            ),
            encryption=AdapterReadiness(
                name="encryption",
                configured=self.encryption_ready,
                healthy=self.encryption_ready,
            ),
            migration=self.migration_status,
            active_snapshot_id=self.active_snapshot_id,
            migration_revision=self.migration_status.current_revision if self.migration_status else None,
        )

    def update_migration_status(self, status: MigrationStatus) -> None:
        self.migration_status = status
        if status.current_revision is not None:
            self.database_ready = True

    def update_active_snapshot_id(self, snapshot_id: str | None) -> None:
        self.active_snapshot_id = snapshot_id

    def liveness(self) -> ProbeResult:
        reasons: list[str] = []
        if self.migration_status is not None and not self.database_ready:
            reasons.append("database_unhealthy")
        if self.migration_status is not None and not self.redis_ready:
            reasons.append("redis_unhealthy")
        status = "ok" if not reasons else "degraded"
        return ProbeResult(status=status, reasons=reasons)

    def readiness(self) -> ProbeResult:
        reasons: list[str] = []
        if self.migration_status is not None and not self.database_ready:
            reasons.append("database_unhealthy")
        if self.migration_status and self.migration_status.current_revision != self.migration_status.expected_revision:
            reasons.append("migration_drift")
        if self.database_ready and self.active_snapshot_id in {"", None}:
            reasons.append("active_snapshot_missing")
        status = "ok" if not reasons else "not_ready"
        return ProbeResult(status=status, reasons=reasons)
