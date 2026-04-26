from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from time import monotonic
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import Connection, Engine, create_engine, delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.control_plane.shadow import ShadowComparisonReport
from backend.control_plane.store import (
    NON_TERMINAL_RUN_STATES,
    AuditEvent,
    ConfigSnapshot,
    ConfigVersionRecord,
    ControlPlaneConflictError,
)

from .contracts import ControlPlaneStore, HandlerRegistry
from .redis import RedisSettings, build_redis_client
from .schema import (
    agent_versions,
    audit_events,
    control_plane_state,
    graph_versions,
    run_snapshot_bindings,
    shadow_reports,
    snapshots,
)
from .telemetry import PersistenceTelemetry, bootstrap_telemetry

CONTROL_PLANE_STORE_MODE_ENV_KEY = "BACKEND_CONTROL_PLANE_STORE_MODE"
HANDLER_REGISTRY_CACHE_TTL_ENV_KEY = "BACKEND_HANDLER_REGISTRY_CACHE_TTL_SECONDS"
SNAPSHOT_ACTIVATION_CHANNEL = "control_plane:snapshot_activated"


class SnapshotActivationBroadcaster(Protocol):
    def publish(self, snapshot_id: str) -> None: ...

    def subscribe(self, callback: Callable[[str], None]) -> None: ...


class ControlPlaneSettings(BaseModel):
    mode: Literal["legacy", "postgres"] = "legacy"
    handler_registry_cache_ttl_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> ControlPlaneSettings:
        mode = os.getenv(CONTROL_PLANE_STORE_MODE_ENV_KEY, "legacy")
        if mode not in ("legacy", "postgres"):
            raise ValueError(
                f"{CONTROL_PLANE_STORE_MODE_ENV_KEY} must be 'legacy' or 'postgres', got '{mode}'"
            )
        ttl_value = os.getenv(HANDLER_REGISTRY_CACHE_TTL_ENV_KEY, "5")
        return cls(
            mode=mode,  # type: ignore[arg-type]
            handler_registry_cache_ttl_seconds=float(ttl_value),
        )


class RedisSnapshotActivationBroadcaster:
    def __init__(
        self,
        *,
        redis_settings: RedisSettings,
        channel: str = SNAPSHOT_ACTIVATION_CHANNEL,
        client: Redis | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._channel = channel
        self._client = client or build_redis_client(redis_settings)
        self._logger = logger or logging.getLogger(__name__)
        self._subscription_started = False
        self._lock = threading.Lock()

    def publish(self, snapshot_id: str) -> None:
        self._client.publish(self._channel, snapshot_id)

    def subscribe(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            if self._subscription_started:
                return
            self._subscription_started = True

        try:
            pubsub = self._client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(self._channel)
        except RedisError:
            self._logger.warning(
                "control_plane_registry_subscription_failed",
                extra={"channel": self._channel},
            )
            return

        def _listen() -> None:
            try:
                for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if data is None:
                        continue
                    callback(str(data))
            except RedisError:
                self._logger.warning(
                    "control_plane_registry_subscription_lost",
                    extra={"channel": self._channel},
                )

        thread = threading.Thread(target=_listen, daemon=True)
        thread.start()


class PostgresControlPlaneStore:
    def __init__(
        self,
        database_url: str,
        *,
        engine: Engine | None = None,
        broadcaster: SnapshotActivationBroadcaster | None = None,
        logger: logging.Logger | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self._engine = engine or create_engine(database_url, future=True, pool_pre_ping=True)
        self._broadcaster = broadcaster
        self._logger = logger or logging.getLogger(__name__)
        self._telemetry = telemetry or bootstrap_telemetry()

    def create_graph_version(
        self,
        *,
        payload: dict[str, object],
        actor: str,
        rationale: str,
    ) -> ConfigVersionRecord:
        with self._telemetry.trace(
            "control_plane_create_graph_version",
            subsystem="control_plane_store",
            operation="create_graph_version",
        ):
            return self._create_version(
                table=graph_versions,
                config_kind="graph",
                payload=payload,
                actor=actor,
                rationale=rationale,
            )

    def create_agent_version(
        self,
        *,
        payload: dict[str, object],
        actor: str,
        rationale: str,
    ) -> ConfigVersionRecord:
        with self._telemetry.trace(
            "control_plane_create_agent_version",
            subsystem="control_plane_store",
            operation="create_agent_version",
        ):
            return self._create_version(
                table=agent_versions,
                config_kind="agent",
                payload=payload,
                actor=actor,
                rationale=rationale,
            )

    def activate(
        self,
        *,
        graph_version_id: str,
        agent_version_ids: dict[str, str],
        actor: str,
        rationale: str,
        comparison_report: ShadowComparisonReport,
        override_rationale: str | None = None,
        expected_active_snapshot_id: str | None = None,
    ) -> ConfigSnapshot:
        with self._telemetry.trace(
            "control_plane_activate",
            subsystem="control_plane_store",
            operation="activate",
            run_id=graph_version_id,
        ):
            if comparison_report.blocked and override_rationale is None:
                raise ValueError(
                    "Activation is blocked until the shadow comparison report is overridden."
                )

            expected_snapshot_id = _normalize_expected_snapshot_id(
                expected_active_snapshot_id,
                comparison_report.active_version_id,
            )
            snapshot_id = str(uuid4())
            evidence_summary = (
                "; ".join(comparison_report.blocking_reasons)
                if comparison_report.blocked
                else "shadow-evidence-passed"
            )

            with self._engine.begin() as connection:
                self._require_version(connection, graph_versions, graph_version_id, "graph")
                for agent_version_id in agent_version_ids.values():
                    self._require_version(connection, agent_versions, agent_version_id, "agent")

                report_id = self._insert_shadow_report(connection, comparison_report)
                previous_snapshot_id = self._load_active_snapshot_id(connection)
                self._insert_snapshot(
                    connection,
                    snapshot_id=snapshot_id,
                    graph_version_id=graph_version_id,
                    agent_version_ids=agent_version_ids,
                    shadow_report_id=report_id,
                    supersedes_snapshot_id=previous_snapshot_id,
                    actor=actor,
                    evidence_summary=evidence_summary,
                )
                self._cas_active_snapshot(
                    connection,
                    expected_active_snapshot_id=expected_snapshot_id,
                    new_snapshot_id=snapshot_id,
                )
                self._insert_audit_event(
                    connection,
                    AuditEvent(
                        event_id=str(uuid4()),
                        action="activate",
                        actor=actor,
                        rationale=override_rationale or rationale,
                        target_id=snapshot_id,
                        evidence_summary=evidence_summary,
                    ),
                )

            snapshot = self._load_snapshot(snapshot_id)
            self._publish_activation(snapshot.snapshot_id)
            return snapshot

    def rollback(
        self,
        *,
        snapshot_id: str,
        actor: str,
        rationale: str,
        expected_active_snapshot_id: str | None = None,
    ) -> ConfigSnapshot:
        with self._telemetry.trace(
            "control_plane_rollback",
            subsystem="control_plane_store",
            operation="rollback",
            run_id=snapshot_id,
        ):
            with self._engine.begin() as connection:
                row = connection.execute(
                    select(snapshots).where(snapshots.c.snapshot_id == snapshot_id)
                ).mappings().first()
                if row is None:
                    raise KeyError(f"Unknown snapshot `{snapshot_id}`.")

                self._cas_active_snapshot(
                    connection,
                    expected_active_snapshot_id=expected_active_snapshot_id,
                    new_snapshot_id=snapshot_id,
                )
                self._insert_audit_event(
                    connection,
                    AuditEvent(
                        event_id=str(uuid4()),
                        action="rollback",
                        actor=actor,
                        rationale=rationale,
                        target_id=snapshot_id,
                        evidence_summary="rollback-reactivated-snapshot",
                    ),
                )

            snapshot = self._load_snapshot(snapshot_id)
            self._publish_activation(snapshot.snapshot_id)
            return snapshot

    def active_snapshot(self) -> ConfigSnapshot:
        with self._telemetry.trace(
            "control_plane_active_snapshot",
            subsystem="control_plane_store",
            operation="active_snapshot",
        ):
            with self._engine.begin() as connection:
                snapshot_id = self._load_active_snapshot_id(connection)
                if snapshot_id is None:
                    raise KeyError("No active snapshot is available.")
                return self._snapshot_from_row(
                    connection.execute(
                        select(snapshots).where(snapshots.c.snapshot_id == snapshot_id)
                    ).mappings().one()
                )

    def pin_run_snapshot(self, run_id: str, snapshot_id: str, status: str) -> None:
        with self._telemetry.trace(
            "control_plane_pin_run_snapshot",
            subsystem="control_plane_store",
            operation="pin_run_snapshot",
            run_id=run_id,
        ):
            stmt = pg_insert(run_snapshot_bindings).values(
                run_id=run_id,
                snapshot_id=snapshot_id,
                status=status,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[run_snapshot_bindings.c.run_id],
                set_={
                    "snapshot_id": stmt.excluded.snapshot_id,
                    "status": stmt.excluded.status,
                    "updated_at": text("now()"),
                },
            )
            with self._engine.begin() as connection:
                connection.execute(stmt)

    def snapshot_for_run(self, run_id: str) -> ConfigSnapshot:
        with self._telemetry.trace(
            "control_plane_snapshot_for_run",
            subsystem="control_plane_store",
            operation="snapshot_for_run",
            run_id=run_id,
        ):
            with self._engine.begin() as connection:
                row = connection.execute(
                    text(
                        """
                        SELECT s.*
                        FROM run_snapshot_bindings rsb
                        JOIN snapshots s ON s.snapshot_id = rsb.snapshot_id
                        WHERE rsb.run_id = :run_id
                        """
                    ),
                    {"run_id": run_id},
                ).mappings().first()
        if row is None:
            raise KeyError(f"Unknown run binding `{run_id}`.")
        return self._snapshot_from_row(row)

    def update_run_status(self, run_id: str, status: str) -> None:
        with self._telemetry.trace(
            "control_plane_update_run_status",
            subsystem="control_plane_store",
            operation="update_run_status",
            run_id=run_id,
        ):
            with self._engine.begin() as connection:
                result = connection.execute(
                    text(
                        """
                        UPDATE run_snapshot_bindings
                        SET status = :status,
                            updated_at = now()
                        WHERE run_id = :run_id
                        """
                    ),
                    {"run_id": run_id, "status": status},
                )
        if result.rowcount == 0:
            raise KeyError(f"Unknown run binding `{run_id}`.")

    def cleanup_retired_snapshots(self) -> list[str]:
        with self._telemetry.trace(
            "control_plane_cleanup_retired_snapshots",
            subsystem="control_plane_store",
            operation="cleanup_retired_snapshots",
        ):
            with self._engine.begin() as connection:
                active_snapshot_id = self._load_active_snapshot_id(connection)
                rows = connection.execute(
                    select(snapshots.c.snapshot_id).order_by(snapshots.c.created_at.asc())
                ).mappings().all()
                referenced_snapshot_ids = {
                    row["snapshot_id"]
                    for row in connection.execute(
                        select(run_snapshot_bindings.c.snapshot_id).where(
                            run_snapshot_bindings.c.status.in_(tuple(NON_TERMINAL_RUN_STATES))
                        )
                    ).mappings()
                }
                deleted: list[str] = []
                for row in rows:
                    snapshot_id = row["snapshot_id"]
                    if snapshot_id == active_snapshot_id or snapshot_id in referenced_snapshot_ids:
                        continue
                    connection.execute(
                        delete(run_snapshot_bindings)
                        .where(run_snapshot_bindings.c.snapshot_id == snapshot_id)
                        .where(~run_snapshot_bindings.c.status.in_(tuple(NON_TERMINAL_RUN_STATES)))
                    )
                    connection.execute(
                        text("DELETE FROM snapshots WHERE snapshot_id = :snapshot_id"),
                        {"snapshot_id": snapshot_id},
                    )
                    deleted.append(snapshot_id)
                return deleted

    def _create_version(
        self,
        *,
        table,
        config_kind: Literal["graph", "agent"],
        payload: dict[str, object],
        actor: str,
        rationale: str,
    ) -> ConfigVersionRecord:
        record_id = str(uuid4())
        with self._engine.begin() as connection:
            version_number = self._next_version_number(connection, table)
            connection.execute(
                pg_insert(table).values(
                    record_id=record_id,
                    version_number=version_number,
                    created_by=actor,
                    rationale=rationale,
                    payload=payload,
                )
            )
            self._insert_audit_event(
                connection,
                AuditEvent(
                    event_id=str(uuid4()),
                    action="create_graph" if config_kind == "graph" else "create_agent",
                    actor=actor,
                    rationale=rationale,
                    target_id=record_id,
                ),
            )
            row = connection.execute(
                select(table).where(table.c.record_id == record_id)
            ).mappings().one()
        return ConfigVersionRecord(
            record_id=row["record_id"],
            config_kind=config_kind,
            version_number=row["version_number"],
            created_by=row["created_by"],
            rationale=row["rationale"],
            created_at=row["created_at"],
            payload=dict(row["payload"]),
        )

    def _insert_shadow_report(
        self,
        connection: Connection,
        report: ShadowComparisonReport,
    ) -> str:
        report_id = str(uuid4())
        connection.execute(
            pg_insert(shadow_reports).values(
                report_id=report_id,
                candidate_version_id=report.candidate_version_id,
                active_version_id=_nullable_snapshot_id(report.active_version_id),
                success_rate_delta=report.success_rate_delta,
                cost_delta_usd=report.cost_delta_usd,
                safety_regressions=report.safety_regressions,
                blocked=report.blocked,
                blocking_reasons=report.blocking_reasons,
                report_payload=json.loads(report.model_dump_json()),
            )
        )
        return report_id

    def _insert_snapshot(
        self,
        connection: Connection,
        *,
        snapshot_id: str,
        graph_version_id: str,
        agent_version_ids: dict[str, str],
        shadow_report_id: str,
        supersedes_snapshot_id: str | None,
        actor: str,
        evidence_summary: str,
    ) -> None:
        connection.execute(
            pg_insert(snapshots).values(
                snapshot_id=snapshot_id,
                graph_version_id=graph_version_id,
                agent_version_ids=agent_version_ids,
                shadow_report_id=shadow_report_id,
                supersedes_snapshot_id=supersedes_snapshot_id,
                created_by=actor,
                evidence_summary=evidence_summary,
            )
        )

    def _cas_active_snapshot(
        self,
        connection: Connection,
        *,
        expected_active_snapshot_id: str | None,
        new_snapshot_id: str,
    ) -> None:
        result = connection.execute(
            text(
                """
                UPDATE control_plane_state
                SET active_snapshot_id = :new_snapshot_id,
                    revision = revision + 1,
                    updated_at = now()
                WHERE state_key = 'global'
                  AND active_snapshot_id IS NOT DISTINCT FROM :expected_active_snapshot_id
                """
            ),
            {
                "new_snapshot_id": new_snapshot_id,
                "expected_active_snapshot_id": expected_active_snapshot_id,
            },
        )
        if result.rowcount != 1:
            raise ControlPlaneConflictError(
                "The active snapshot changed before this operation could commit."
            )

    def _insert_audit_event(self, connection: Connection, event: AuditEvent) -> None:
        connection.execute(
            pg_insert(audit_events).values(
                event_id=event.event_id,
                action=event.action,
                actor=event.actor,
                rationale=event.rationale,
                target_id=event.target_id,
                evidence_summary=event.evidence_summary,
            )
        )

    def _next_version_number(self, connection: Connection, table) -> int:
        row = connection.execute(
            select(text("COALESCE(MAX(version_number), 0) + 1 AS next_version")).select_from(table)
        ).mappings().one()
        return int(row["next_version"])

    def _require_version(
        self,
        connection: Connection,
        table,
        record_id: str,
        config_kind: str,
    ) -> None:
        row = connection.execute(
            select(table.c.record_id).where(table.c.record_id == record_id)
        ).first()
        if row is None:
            raise KeyError(f"Unknown {config_kind} version `{record_id}`.")

    def _load_active_snapshot_id(self, connection: Connection) -> str | None:
        row = connection.execute(
            select(control_plane_state.c.active_snapshot_id).where(
                control_plane_state.c.state_key == "global"
            )
        ).mappings().one()
        return row["active_snapshot_id"]

    def _load_snapshot(self, snapshot_id: str) -> ConfigSnapshot:
        with self._engine.begin() as connection:
            row = connection.execute(
                select(snapshots).where(snapshots.c.snapshot_id == snapshot_id)
            ).mappings().first()
        if row is None:
            raise KeyError(f"Unknown snapshot `{snapshot_id}`.")
        return self._snapshot_from_row(row)

    def _snapshot_from_row(self, row: Any) -> ConfigSnapshot:
        return ConfigSnapshot(
            snapshot_id=row["snapshot_id"],
            graph_version_id=row["graph_version_id"],
            agent_version_ids=dict(row["agent_version_ids"]),
            created_at=row["created_at"],
            created_by=row["created_by"],
            evidence_summary=row["evidence_summary"],
        )

    def _publish_activation(self, snapshot_id: str) -> None:
        if self._broadcaster is None:
            return
        try:
            self._broadcaster.publish(snapshot_id)
        except RedisError:
            self._logger.warning(
                "control_plane_activation_publish_failed",
                extra={"snapshot_id": snapshot_id},
            )


class SnapshotDrivenHandlerRegistry:
    def __init__(
        self,
        database_url: str,
        *,
        engine: Engine | None = None,
        broadcaster: SnapshotActivationBroadcaster | None = None,
        cache_ttl_seconds: float = 5.0,
        logger: logging.Logger | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self._engine = engine or create_engine(database_url, future=True, pool_pre_ping=True)
        self._broadcaster = broadcaster
        self._cache_ttl_seconds = cache_ttl_seconds
        self._logger = logger or logging.getLogger(__name__)
        self._telemetry = telemetry or bootstrap_telemetry()
        self._lock = threading.Lock()
        self._cached_snapshot_id: str | None = None
        self._cached_handlers: dict[str, str] = {}
        self._cache_loaded_at = 0.0
        self._subscription_started = False

    def resolve(self, handler_name: str) -> str | None:
        with self._telemetry.trace(
            "handler_registry_resolve",
            subsystem="handler_registry",
            operation="resolve",
        ):
            self._ensure_subscription()

            with self._lock:
                if not self._cache_stale():
                    return self._cached_handlers.get(handler_name)

            snapshot_id, handlers = self._load_active_handlers()
            with self._lock:
                self._cached_snapshot_id = snapshot_id
                self._cached_handlers = handlers
                self._cache_loaded_at = monotonic()
                return self._cached_handlers.get(handler_name)

    def invalidate(self, snapshot_id: str | None = None) -> None:
        with self._telemetry.trace(
            "handler_registry_invalidate",
            subsystem="handler_registry",
            operation="invalidate",
            run_id=snapshot_id,
        ):
            with self._lock:
                if snapshot_id is not None and snapshot_id == self._cached_snapshot_id:
                    return
                self._cached_snapshot_id = None
                self._cached_handlers = {}
                self._cache_loaded_at = 0.0

    def _cache_stale(self) -> bool:
        if self._cached_snapshot_id is None:
            return True
        return monotonic() - self._cache_loaded_at >= self._cache_ttl_seconds

    def _load_active_handlers(self) -> tuple[str, dict[str, str]]:
        from backend.control_plane.graph import GraphConfigVersion

        with self._engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT s.snapshot_id, gv.payload
                    FROM control_plane_state cps
                    JOIN snapshots s ON s.snapshot_id = cps.active_snapshot_id
                    JOIN graph_versions gv ON gv.record_id = s.graph_version_id
                    WHERE cps.state_key = 'global'
                    """
                )
            ).mappings().first()
        if row is None:
            raise KeyError("No active snapshot is available.")

        graph = GraphConfigVersion.model_validate(row["payload"])
        handlers = {
            ref.handler_name: ref.handler_kind
            for ref in graph.route_handlers
        }
        return str(row["snapshot_id"]), handlers

    def _ensure_subscription(self) -> None:
        if self._broadcaster is None or self._subscription_started:
            return
        self._subscription_started = True
        self._broadcaster.subscribe(self.invalidate)


def build_snapshot_activation_broadcaster(
    redis_settings: RedisSettings,
    *,
    logger: logging.Logger | None = None,
) -> SnapshotActivationBroadcaster:
    return RedisSnapshotActivationBroadcaster(redis_settings=redis_settings, logger=logger)


def build_control_plane_store(
    *,
    database_url: str | None,
    legacy_store: ControlPlaneStore | None,
    broadcaster: SnapshotActivationBroadcaster | None = None,
    settings: ControlPlaneSettings | None = None,
    logger: logging.Logger | None = None,
    telemetry: PersistenceTelemetry | None = None,
) -> ControlPlaneStore:
    resolved = settings or ControlPlaneSettings.from_env()
    if resolved.mode == "legacy":
        if legacy_store is None:
            raise RuntimeError("Legacy control-plane mode requires an in-memory test double.")
        return legacy_store
    if not database_url:
        raise RuntimeError(
            f"{CONTROL_PLANE_STORE_MODE_ENV_KEY}=postgres requires a configured database URL"
        )
    return PostgresControlPlaneStore(
        database_url,
        broadcaster=broadcaster,
        logger=logger,
        telemetry=telemetry,
    )


def build_handler_registry(
    *,
    database_url: str | None,
    legacy_registry: HandlerRegistry | None,
    broadcaster: SnapshotActivationBroadcaster | None = None,
    settings: ControlPlaneSettings | None = None,
    logger: logging.Logger | None = None,
    telemetry: PersistenceTelemetry | None = None,
) -> HandlerRegistry:
    resolved = settings or ControlPlaneSettings.from_env()
    if resolved.mode == "legacy":
        if legacy_registry is None:
            raise RuntimeError("Legacy handler-registry mode requires an in-memory test double.")
        return legacy_registry
    if not database_url:
        raise RuntimeError(
            f"{CONTROL_PLANE_STORE_MODE_ENV_KEY}=postgres requires a configured database URL"
        )
    return SnapshotDrivenHandlerRegistry(
        database_url,
        broadcaster=broadcaster,
        cache_ttl_seconds=resolved.handler_registry_cache_ttl_seconds,
        logger=logger,
        telemetry=telemetry,
    )

def _normalize_expected_snapshot_id(
    explicit_snapshot_id: str | None,
    observed_snapshot_id: str | None,
) -> str | None:
    if explicit_snapshot_id is not None:
        return explicit_snapshot_id
    return _nullable_snapshot_id(observed_snapshot_id)


def _nullable_snapshot_id(snapshot_id: str | None) -> str | None:
    if snapshot_id in {None, "", "none"}:
        return None
    return snapshot_id
