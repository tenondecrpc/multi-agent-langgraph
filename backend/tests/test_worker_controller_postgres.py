from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus

import psycopg
import pytest
from psycopg import errors as psycopg_errors
from psycopg.rows import dict_row
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.engine import make_url

from alembic import command
from backend.persistence import RedisWorkerController, WorkerControllerSettings, build_alembic_config
from backend.platform.queue import QueuedJob


class FakeRedis:
    def __init__(self) -> None:
        self.fail_commands = False
        self._strings: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._sets: dict[str, set[str]] = {}

    def delete(self, *keys: str) -> int:
        self._maybe_fail()
        deleted = 0
        for key in keys:
            deleted += int(self._strings.pop(key, None) is not None)
        return deleted

    def exists(self, key: str) -> int:
        self._maybe_fail()
        return int(key in self._strings)

    def get(self, key: str) -> str | None:
        self._maybe_fail()
        return self._strings.get(key)

    def hdel(self, name: str, *keys: str) -> int:
        self._maybe_fail()
        mapping = self._hashes.setdefault(name, {})
        deleted = 0
        for key in keys:
            deleted += int(mapping.pop(key, None) is not None)
        return deleted

    def hget(self, name: str, key: str) -> str | None:
        self._maybe_fail()
        return self._hashes.get(name, {}).get(key)

    def hset(self, name: str, key: str, value: str) -> int:
        self._maybe_fail()
        mapping = self._hashes.setdefault(name, {})
        mapping[key] = value
        return 1

    def incrby(self, key: str, amount: int = 1) -> int:
        self._maybe_fail()
        current = int(self._strings.get(key, "0")) + amount
        self._strings[key] = str(current)
        return current

    def decrby(self, key: str, amount: int = 1) -> int:
        return self.incrby(key, -amount)

    def publish(self, channel: str, message: str) -> int:
        self._maybe_fail()
        return 1

    def sadd(self, name: str, *values: str) -> int:
        self._maybe_fail()
        members = self._sets.setdefault(name, set())
        before = len(members)
        members.update(values)
        return len(members) - before

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._maybe_fail()
        self._strings[key] = value
        return True

    def srem(self, name: str, *values: str) -> int:
        self._maybe_fail()
        members = self._sets.setdefault(name, set())
        removed = 0
        for value in values:
            removed += int(value in members)
            members.discard(value)
        return removed

    def smembers(self, name: str) -> set[str]:
        self._maybe_fail()
        return set(self._sets.get(name, set()))

    def _maybe_fail(self) -> None:
        if self.fail_commands:
            raise RedisConnectionError("redis unavailable")


@pytest.fixture()
def temporary_postgres() -> str:
    with TemporaryDirectory(prefix="backend-pg-") as temp_dir:
        base_dir = Path(temp_dir)
        data_dir = base_dir / "data"
        log_path = base_dir / "postgres.log"
        socket_dir = base_dir / "socket"
        socket_dir.mkdir(parents=True, exist_ok=True)
        port = 55435

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


def test_shared_redis_counters_enforce_tenant_concurrency_across_replicas(
    migrated_postgres: str,
) -> None:
    redis = FakeRedis()
    settings = WorkerControllerSettings(
        mode="redis",
        per_tenant_concurrency=1,
        starvation_threshold_seconds=300,
    )
    controller_a = RedisWorkerController(
        migrated_postgres,
        redis_client=redis,
        settings=settings,
    )
    controller_b = RedisWorkerController(
        migrated_postgres,
        redis_client=redis,
        settings=settings,
    )

    job_a = _job(job_id="job-a", tenant_id="tenant-alpha", enqueued_at=0)
    job_b = _job(job_id="job-b", tenant_id="tenant-alpha", enqueued_at=10)

    controller_a.assign("worker-a", job_a)

    assert controller_b.select_next_job([job_b], now=20) is None


def test_starvation_threshold_uses_shared_redis_in_flight_counters(
    migrated_postgres: str,
) -> None:
    redis = FakeRedis()
    controller = RedisWorkerController(
        migrated_postgres,
        redis_client=redis,
        settings=WorkerControllerSettings(
            mode="redis",
            per_tenant_concurrency=1,
            starvation_threshold_seconds=300,
        ),
    )
    jobs = [
        _job(job_id="job-b", tenant_id="tenant-b", enqueued_at=10),
        _job(job_id="job-a", tenant_id="tenant-a", enqueued_at=0),
    ]

    selected = controller.select_next_job(jobs, now=400)

    assert selected is not None
    assert selected.job_id == "job-a"


def test_drain_lease_blocks_new_assignments_and_releases_checkpoint(
    migrated_postgres: str,
) -> None:
    redis = FakeRedis()
    controller = RedisWorkerController(
        migrated_postgres,
        redis_client=redis,
        settings=WorkerControllerSettings(mode="redis"),
    )
    job = _job(job_id="job-1", tenant_id="tenant-alpha", enqueued_at=1)
    controller.assign("worker-1", job)

    lease = controller.begin_drain("worker-1")
    assert lease.accepting_new_jobs is False
    assert lease.active_job_id == "job-1"
    assert "worker-1" in controller.draining_workers

    with pytest.raises(ValueError, match="draining"):
        controller.assign("worker-1", _job(job_id="job-2", tenant_id="tenant-beta", enqueued_at=2))

    checkpointed = controller.checkpoint_and_release("worker-1", checkpoint_ref="checkpoint-1")

    assert checkpointed.checkpoint_ref == "checkpoint-1"
    assert "worker-1" not in controller.draining_workers


def test_terminal_failure_persists_dlq_record_across_redis_outage(
    migrated_postgres: str,
) -> None:
    redis = FakeRedis()
    controller = RedisWorkerController(
        migrated_postgres,
        redis_client=redis,
        settings=WorkerControllerSettings(mode="redis"),
    )
    controller.assign(
        "worker-1",
        _job(
            job_id="job-1",
            tenant_id="tenant-alpha",
            enqueued_at=1,
            checkpoint_ref="checkpoint-1",
        ),
    )
    redis.fail_commands = True

    record = controller.capture_terminal_failure("worker-1", "retry_budget_exhausted")

    assert record.checkpoint_ref == "checkpoint-1"
    redis.fail_commands = False
    records = controller.list_dead_letter_records()
    assert len(records) == 1
    assert records[0].job_id == "job-1"
    assert records[0].failure_reason == "retry_budget_exhausted"

    with _connect(migrated_postgres) as connection:
        count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM dead_letter_records"
        ).fetchone()

    assert count_row["count"] == 1


def test_dead_letter_rows_stay_tenant_scoped_under_rls(
    migrated_postgres: str,
) -> None:
    redis = FakeRedis()
    controller = RedisWorkerController(
        migrated_postgres,
        redis_client=redis,
        settings=WorkerControllerSettings(mode="redis"),
    )
    controller.assign(
        "worker-1",
        _job(
            job_id="job-rls",
            tenant_id="tenant-alpha",
            enqueued_at=1,
        ),
    )
    controller.capture_terminal_failure("worker-1", "tenant_scope_validation")

    with _connect(migrated_postgres) as connection:
        connection.execute("DROP ROLE IF EXISTS app_runtime")
        connection.execute("CREATE ROLE app_runtime LOGIN")
        connection.execute("GRANT USAGE ON SCHEMA public, app TO app_runtime")
        connection.execute("GRANT SELECT, INSERT ON dead_letter_records TO app_runtime")

    with _connect(migrated_postgres) as connection:
        connection.execute("SET ROLE app_runtime")
        connection.execute("SELECT set_config('app.tenant_id', 'tenant-beta', false)")
        connection.execute("SELECT set_config('app.team_id', '*', false)")
        visible = connection.execute("SELECT COUNT(*) AS count FROM dead_letter_records").fetchone()
        assert visible["count"] == 0

    with _connect(migrated_postgres) as connection:
        connection.execute("SET ROLE app_runtime")
        connection.execute("SELECT set_config('app.tenant_id', 'tenant-alpha', false)")
        connection.execute("SELECT set_config('app.team_id', '*', false)")
        visible = connection.execute("SELECT COUNT(*) AS count FROM dead_letter_records").fetchone()
        assert visible["count"] == 1

    with _connect(migrated_postgres) as connection:
        connection.execute("SET ROLE app_runtime")
        connection.execute("SELECT set_config('app.tenant_id', 'tenant-beta', false)")
        connection.execute("SELECT set_config('app.team_id', '*', false)")
        with pytest.raises(psycopg_errors.InsufficientPrivilege):
            connection.execute(
                """
                INSERT INTO dead_letter_records (
                    job_id, tenant_id, team_id, run_id, queue_name, worker_id, failure_reason
                ) VALUES (
                    'rogue-job', 'tenant-alpha', 'team-core', 'run-rogue', 'ticket-runs',
                    'worker-rogue', 'cross-tenant-write'
                )
                """
            )


def _job(
    *,
    job_id: str,
    tenant_id: str,
    enqueued_at: int,
    checkpoint_ref: str | None = None,
) -> QueuedJob:
    return QueuedJob(
        job_id=job_id,
        tenant_id=tenant_id,
        team_id="team-core",
        run_id=f"run-{job_id}",
        enqueued_at=enqueued_at,
        checkpoint_ref=checkpoint_ref,
    )


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
    subprocess.run(command_args, check=True, capture_output=True, text=True)
