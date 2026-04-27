from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus

import psycopg
import pytest
from psycopg import errors as psycopg_errors
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from alembic import command
from backend.persistence import build_alembic_config
from backend.persistence.runs import (
    PostgresRunRepository,
    RunNotFoundError,
    RunRepositorySettings,
    TenantContextMissingError,
    build_run_repository,
)
from backend.persistence.testing.runtime import InMemoryRunRepository
from backend.runtime.models import (
    EscalationReason,
    PlanningRequest,
    RunNode,
    RunStatus,
    TenantContext,
    TicketRunState,
)


@pytest.fixture()
def temporary_postgres() -> str:
    with TemporaryDirectory(prefix="backend-pg-") as temp_dir:
        base_dir = Path(temp_dir)
        data_dir = base_dir / "data"
        log_path = base_dir / "postgres.log"
        socket_dir = base_dir / "socket"
        socket_dir.mkdir(parents=True, exist_ok=True)
        port = 55433

        try:
            _run(["initdb", "-D", str(data_dir), "-U", "postgres", "-A", "trust"])
            _run(
                [
                    "pg_ctl",
                    "-D",
                    str(data_dir),
                    "-l",
                    str(log_path),
                    "-o",
                    f"-p {port} -k {socket_dir} -c listen_addresses=",
                    "-w",
                    "start",
                ]
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip().splitlines()
            detail = stderr[-1] if stderr else str(exc)
            pytest.skip(f"ephemeral postgres bootstrap unavailable in this environment: {detail}")
        try:
            quoted_socket_dir = quote_plus(str(socket_dir))
            yield f"postgresql+psycopg://postgres@/postgres?host={quoted_socket_dir}&port={port}"
        finally:
            if data_dir.exists():
                subprocess.run(
                    ["pg_ctl", "-D", str(data_dir), "-m", "immediate", "stop"],
                    check=False,
                    capture_output=True,
                    text=True,
                )


@pytest.fixture()
def migrated_postgres(temporary_postgres: str) -> str:
    command.upgrade(build_alembic_config(temporary_postgres), "head")
    return temporary_postgres


def _new_run(
    *,
    tenant_id: str = "tenant-alpha",
    team_id: str = "team-core",
    ticket_key: str = "ENG-1",
    summary: str = "Resume across pod restarts",
) -> TicketRunState:
    planning = PlanningRequest(
        tenant_id=tenant_id,
        team_id=team_id,
        ticket_key=ticket_key,
        summary=summary,
    )
    return TicketRunState.new(planning)


def test_build_run_repository_defaults_to_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BACKEND_RUN_REPOSITORY_MODE", raising=False)
    legacy = InMemoryRunRepository()
    repository = build_run_repository(database_url=None, legacy_repository=legacy)
    assert repository is legacy


def test_build_run_repository_postgres_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    legacy = InMemoryRunRepository()
    with pytest.raises(RuntimeError, match="requires a configured database URL"):
        build_run_repository(
            database_url=None,
            legacy_repository=legacy,
            settings=RunRepositorySettings(mode="postgres"),
        )


def test_postgres_repository_load_requires_tenant_context() -> None:
    repository = PostgresRunRepository.__new__(PostgresRunRepository)
    repository._engine = None  # type: ignore[attr-defined]
    repository._logger = logging.getLogger(__name__)  # type: ignore[attr-defined]
    repository.checkpoint_saver = None

    with pytest.raises(TenantContextMissingError):
        repository.load("thread-1")

    with pytest.raises(TenantContextMissingError):
        repository.resume("thread-1")


def test_postgres_repository_persists_and_resumes_across_instances(
    migrated_postgres: str,
) -> None:
    repository = PostgresRunRepository(migrated_postgres)
    run = _new_run()
    paused = repository.pause(
        run,
        node=RunNode.TESTER,
        reason=EscalationReason.MISSING_OR_FAILING_REQUIRED_TESTS,
        escalation_sinks=_all_escalation_sinks(),
    )

    assert paused.status == RunStatus.PAUSED
    assert paused.escalation_sink == "ops://quality"

    # Simulate a second worker pod loading the same run.
    second_repository = PostgresRunRepository(migrated_postgres)
    context = TenantContext(tenant_id=run.tenant_id, team_id=run.team_id)
    resumed = second_repository.resume(run.thread_id, tenant_context=context)

    assert resumed.run_id == paused.run_id
    assert resumed.thread_id == paused.thread_id
    assert resumed.config_snapshot_id == paused.config_snapshot_id
    assert resumed.paused_at_node is None
    assert resumed.escalation_reason is None
    assert resumed.status == RunStatus.ACTIVE


def test_postgres_repository_resume_missing_run_raises(migrated_postgres: str) -> None:
    repository = PostgresRunRepository(migrated_postgres)
    context = TenantContext(tenant_id="tenant-alpha", team_id="team-core")
    with pytest.raises(RunNotFoundError):
        repository.resume("missing-thread", tenant_context=context)


def test_application_filter_blocks_cross_tenant_access(migrated_postgres: str) -> None:
    repository = PostgresRunRepository(migrated_postgres)
    run_a = _new_run(tenant_id="tenant-alpha", team_id="team-core", ticket_key="ENG-10")
    repository.save(run_a)

    cross_tenant = TenantContext(tenant_id="tenant-beta", team_id="team-core")
    assert repository.load(run_a.thread_id, tenant_context=cross_tenant) is None

    cross_team = TenantContext(tenant_id="tenant-alpha", team_id="team-other")
    assert repository.load(run_a.thread_id, tenant_context=cross_team) is None

    same = TenantContext(tenant_id="tenant-alpha", team_id="team-core")
    assert repository.load(run_a.thread_id, tenant_context=same) is not None


def test_row_level_security_blocks_cross_tenant_reads_for_non_bypass_role(
    migrated_postgres: str,
) -> None:
    # Arrange: seed a row via the superuser-backed repository.
    repository = PostgresRunRepository(migrated_postgres)
    run_a = _new_run(tenant_id="tenant-alpha", team_id="team-core", ticket_key="ENG-20")
    repository.save(run_a)

    # Create a non-BYPASSRLS role. Superusers always bypass RLS, so the deployed
    # application role must be a normal LOGIN role like this one.
    with _connect(migrated_postgres) as connection:
        connection.execute("DROP ROLE IF EXISTS app_runtime")
        connection.execute("CREATE ROLE app_runtime LOGIN")
        connection.execute("GRANT USAGE ON SCHEMA public, app TO app_runtime")
        connection.execute("GRANT SELECT, INSERT, UPDATE ON runs TO app_runtime")

    with _connect(migrated_postgres) as connection:
        connection.execute("SET ROLE app_runtime")
        connection.execute("SELECT set_config('app.tenant_id', 'tenant-beta', false)")
        connection.execute("SELECT set_config('app.team_id', 'team-core', false)")
        visible = connection.execute("SELECT COUNT(*) AS count FROM runs").fetchone()
        assert visible["count"] == 0

    with _connect(migrated_postgres) as connection:
        connection.execute("SET ROLE app_runtime")
        connection.execute("SELECT set_config('app.tenant_id', 'tenant-alpha', false)")
        connection.execute("SELECT set_config('app.team_id', 'team-core', false)")
        visible = connection.execute("SELECT COUNT(*) AS count FROM runs").fetchone()
        assert visible["count"] == 1

    # Insert with mismatched tenant GUC is rejected by the WITH CHECK policy.
    with _connect(migrated_postgres) as connection:
        connection.execute("SET ROLE app_runtime")
        connection.execute("SELECT set_config('app.tenant_id', 'tenant-beta', false)")
        connection.execute("SELECT set_config('app.team_id', 'team-core', false)")
        with pytest.raises(psycopg_errors.InsufficientPrivilege):
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, thread_id, tenant_id, team_id, repo_id, ticket_key,
                    status, current_node, config_snapshot_id, graph_profile_id,
                    catalog_version
                ) VALUES (
                    'rogue', 'tenant-alpha:X:rogue', 'tenant-alpha', 'team-core',
                    'repo', 'ENG-X', 'planning', 'intake', 'snap', 'prof', 'cat'
                )
                """
            )


def _all_escalation_sinks() -> dict[str, str]:
    return {
        EscalationReason.UNRESOLVED_AMBIGUITY.value: "ops://clarification",
        EscalationReason.TEST_RETRY_BUDGET_EXHAUSTED.value: "ops://testing",
        EscalationReason.REVIEW_BUDGET_EXHAUSTED.value: "ops://review",
        EscalationReason.MISSING_OR_FAILING_REQUIRED_TESTS.value: "ops://quality",
        EscalationReason.DIFF_TOO_LARGE.value: "ops://diff-guard",
        EscalationReason.MERGE_CONFLICT_DETECTED.value: "ops://merge-conflict",
        EscalationReason.INVALID_ROUTE_ATTEMPT.value: "ops://workflow-guard",
        EscalationReason.MISSING_ESCALATION_SINK.value: "ops://workflow-guard",
    }


def _connect(database_url: str) -> psycopg.Connection:
    parsed = make_url(database_url)
    socket_path = parsed.query.get("host", "")
    port = parsed.query.get("port", "")
    user = parsed.username or "postgres"
    database = parsed.database or "postgres"
    return psycopg.connect(
        f"dbname={database} user={user} host={socket_path} port={port}",
        autocommit=True,
        row_factory=dict_row,
    )


def _run(command_args: list[str]) -> None:
    try:
        subprocess.run(command_args, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        pytest.skip(f"ephemeral postgres bootstrap unavailable in this environment: {exc}")
