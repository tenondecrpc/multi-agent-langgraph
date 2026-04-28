from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.persistence.testing.runtime import required_phase_one_escalation_reasons
from backend.runtime.models import (
    EscalationReason,
    RunNode,
    RunStatus,
    TenantContext,
    TicketRunState,
)

from .contracts import RunRepository
from .db import tenant_guc_values
from .schema import runs
from .telemetry import PersistenceTelemetry, bootstrap_telemetry

RUN_REPOSITORY_MODE_ENV_KEY = "BACKEND_RUN_REPOSITORY_MODE"
RUN_CHECKPOINT_URL_ENV_KEY = "BACKEND_RUN_CHECKPOINT_DATABASE_URL"

RunRepositoryMode = Literal["legacy", "postgres"]


class RunRepositorySettings(BaseModel):
    mode: RunRepositoryMode = "legacy"

    @classmethod
    def from_env(cls) -> RunRepositorySettings:
        value = os.getenv(RUN_REPOSITORY_MODE_ENV_KEY, "legacy")
        if value not in ("legacy", "postgres"):
            raise ValueError(
                f"{RUN_REPOSITORY_MODE_ENV_KEY} must be 'legacy' or 'postgres', got '{value}'"
            )
        return cls(mode=value)  # type: ignore[arg-type]


class TenantContextMissingError(RuntimeError):
    """PostgresRunRepository requires explicit tenant context to satisfy row-level security."""


class RunNotFoundError(LookupError):
    """Requested run is not visible under the active tenant context."""


class PostgresCheckpointSaverHandle:
    """Opaque handle for binding a LangGraph PostgresSaver at graph-compile time."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def build_saver(self):  # pragma: no cover - integration-facing
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg import Connection
        from psycopg.rows import dict_row

        # psycopg does not understand the +psycopg dialect prefix used by SQLAlchemy.
        conninfo = self.database_url.replace("postgresql+psycopg://", "postgresql://")
        conn = Connection.connect(
            conninfo, autocommit=True, prepare_threshold=0, row_factory=dict_row
        )
        return PostgresSaver(conn)


class PostgresRunRepository:
    def __init__(
        self,
        database_url: str,
        *,
        engine: Engine | None = None,
        logger: logging.Logger | None = None,
        checkpoint_saver: PostgresCheckpointSaverHandle | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self._engine = engine or create_engine(database_url, future=True, pool_pre_ping=True)
        self._logger = logger or logging.getLogger(__name__)
        self.checkpoint_saver = checkpoint_saver
        self._telemetry = telemetry or bootstrap_telemetry()

    def save(self, run: TicketRunState) -> TicketRunState:
        snapshot = run.model_copy(deep=True)
        with self._telemetry.trace(
            "run_repository_save",
            subsystem="run_repository",
            operation="save",
            tenant_id=snapshot.tenant_id,
            team_id=snapshot.team_id,
            run_id=snapshot.run_id,
        ):
            with self._scoped_transaction(snapshot.tenant_id, snapshot.team_id) as connection:
                self._upsert(connection, snapshot)
        self._log("run_saved", snapshot)
        return snapshot

    def load(
        self,
        thread_id: str,
        *,
        tenant_context: TenantContext | None = None,
    ) -> TicketRunState | None:
        if tenant_context is None:
            raise TenantContextMissingError(
                "PostgresRunRepository.load requires an explicit tenant_context to satisfy "
                "row-level security policies on the runs table."
            )
        with self._telemetry.trace(
            "run_repository_load",
            subsystem="run_repository",
            operation="load",
            tenant_id=tenant_context.tenant_id,
            team_id=tenant_context.team_id,
        ):
            with self._scoped_transaction(tenant_context.tenant_id, tenant_context.team_id) as connection:
                row = connection.execute(
                    text(
                        """
                        SELECT run_payload FROM runs
                        WHERE thread_id = :thread_id
                          AND tenant_id = :tenant_id
                          AND team_id = :team_id
                        """
                    ),
                    {
                        "thread_id": thread_id,
                        "tenant_id": tenant_context.tenant_id,
                        "team_id": tenant_context.team_id,
                    },
                ).fetchone()
        if row is None:
            return None
        return TicketRunState.model_validate(row._mapping["run_payload"])

    def validate_escalation_sinks(
        self,
        escalation_sinks: Mapping[str, str],
        required_reasons: tuple[EscalationReason, ...] | None = None,
    ) -> None:
        with self._telemetry.trace(
            "run_repository_validate_escalation_sinks",
            subsystem="run_repository",
            operation="validate_escalation_sinks",
        ):
            reasons = required_reasons or required_phase_one_escalation_reasons()
            missing = [reason.value for reason in reasons if reason.value not in escalation_sinks]
            if missing:
                raise ValueError(
                    "Every phase-1 escalation reason must map to a registered sink. "
                    f"Missing: {', '.join(sorted(missing))}"
                )

    def pause(
        self,
        run: TicketRunState,
        node: RunNode,
        reason: EscalationReason,
        escalation_sinks: Mapping[str, str],
    ) -> TicketRunState:
        self.validate_escalation_sinks(escalation_sinks)
        paused = run.model_copy(deep=True)
        paused.status = RunStatus.PAUSED
        paused.paused_at_node = node
        paused.escalation_reason = reason
        paused.escalation_sink = escalation_sinks[reason.value]
        with self._telemetry.trace(
            "run_repository_pause",
            subsystem="run_repository",
            operation="pause",
            tenant_id=paused.tenant_id,
            team_id=paused.team_id,
            run_id=paused.run_id,
        ):
            with self._scoped_transaction(paused.tenant_id, paused.team_id) as connection:
                self._upsert(connection, paused)
        self._log("run_paused", paused)
        return paused

    def resume(
        self,
        thread_id: str,
        *,
        tenant_context: TenantContext | None = None,
    ) -> TicketRunState:
        if tenant_context is None:
            raise TenantContextMissingError(
                "PostgresRunRepository.resume requires an explicit tenant_context to satisfy "
                "row-level security policies on the runs table."
            )
        with self._telemetry.trace(
            "run_repository_resume",
            subsystem="run_repository",
            operation="resume",
            tenant_id=tenant_context.tenant_id,
            team_id=tenant_context.team_id,
        ):
            with self._scoped_transaction(tenant_context.tenant_id, tenant_context.team_id) as connection:
                locked = connection.execute(
                    text(
                        """
                        SELECT run_payload FROM runs
                        WHERE thread_id = :thread_id
                          AND tenant_id = :tenant_id
                          AND team_id = :team_id
                        FOR UPDATE
                        """
                    ),
                    {
                        "thread_id": thread_id,
                        "tenant_id": tenant_context.tenant_id,
                        "team_id": tenant_context.team_id,
                    },
                ).fetchone()
                if locked is None:
                    raise RunNotFoundError(
                        f"No run found for thread `{thread_id}` under tenant "
                        f"`{tenant_context.tenant_id}`/`{tenant_context.team_id}`."
                    )
                resumed = TicketRunState.model_validate(locked._mapping["run_payload"])
                resumed.clear_pause()
                self._upsert(connection, resumed)
        self._log("run_resumed", resumed)
        return resumed

    @contextmanager
    def _scoped_transaction(self, tenant_id: str, team_id: str) -> Iterator[Connection]:
        with self._engine.begin() as connection:
            for key, value in tenant_guc_values(tenant_id=tenant_id, team_id=team_id).items():
                connection.execute(
                    text("SELECT set_config(:key, :value, true)"),
                    {"key": key, "value": value},
                )
            yield connection

    def _upsert(self, connection: Connection, run: TicketRunState) -> None:
        values = _runs_row_from_state(run)
        stmt = pg_insert(runs).values(**values)
        update_columns: dict[str, Any] = {
            column: stmt.excluded[column]
            for column in values
            if column != "run_id"
        }
        update_columns["updated_at"] = text("now()")
        stmt = stmt.on_conflict_do_update(
            index_elements=[runs.c.run_id],
            set_=update_columns,
        )
        connection.execute(stmt)

    def _log(self, event: str, run: TicketRunState) -> None:
        self._logger.info(
            event,
            extra={
                "tenant_id": run.tenant_id,
                "team_id": run.team_id,
                "run_id": run.run_id,
                "thread_id": run.thread_id,
                "status": run.status.value,
                "paused_at_node": run.paused_at_node.value if run.paused_at_node else None,
                "escalation_reason": run.escalation_reason.value if run.escalation_reason else None,
                "subsystem": "run_repository",
            },
        )


def build_run_repository(
    *,
    database_url: str | None,
    legacy_repository: RunRepository | None,
    settings: RunRepositorySettings | None = None,
    checkpoint_saver: PostgresCheckpointSaverHandle | None = None,
    logger: logging.Logger | None = None,
    telemetry: PersistenceTelemetry | None = None,
) -> RunRepository:
    resolved = settings or RunRepositorySettings.from_env()
    if resolved.mode == "legacy":
        if legacy_repository is None:
            raise RuntimeError("Legacy run repository mode requires an in-memory test double.")
        return legacy_repository
    if not database_url:
        raise RuntimeError(
            f"{RUN_REPOSITORY_MODE_ENV_KEY}=postgres requires a configured database URL"
        )
    return PostgresRunRepository(
        database_url,
        logger=logger,
        checkpoint_saver=checkpoint_saver,
        telemetry=telemetry,
    )


def build_checkpoint_saver_handle(
    database_url: str | None,
) -> PostgresCheckpointSaverHandle | None:
    override = os.getenv(RUN_CHECKPOINT_URL_ENV_KEY)
    resolved_url = override or database_url
    if not resolved_url:
        return None
    return PostgresCheckpointSaverHandle(resolved_url)


def _runs_row_from_state(run: TicketRunState) -> dict[str, Any]:
    payload = json.loads(run.model_dump_json())
    return {
        "run_id": run.run_id,
        "thread_id": run.thread_id,
        "tenant_id": run.tenant_id,
        "team_id": run.team_id,
        "repo_id": run.repo_id,
        "ticket_key": run.ticket_key,
        "status": run.status.value,
        "current_node": run.current_node.value,
        "paused_at_node": run.paused_at_node.value if run.paused_at_node else None,
        "escalation_reason": run.escalation_reason.value if run.escalation_reason else None,
        "escalation_sink": run.escalation_sink,
        "config_snapshot_id": run.config_snapshot_id,
        "graph_profile_id": run.graph_profile_id,
        "catalog_version": run.catalog_version,
        "state_schema_version": run.state_schema_version,
        "artifact_hashes": dict(run.artifact_hashes),
        "run_payload": payload,
    }
