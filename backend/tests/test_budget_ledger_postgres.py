from __future__ import annotations

import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus

import psycopg
import pytest
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from alembic import command
from backend.governance.budget import BudgetCaps, BudgetContext, BudgetExceededError
from backend.persistence import PostgresBudgetLedger, build_alembic_config
from backend.persistence.redis import RedisSettings


class FakeRedis:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._strings: dict[str, str] = {}

    def eval(self, script: str, numkeys: int, *keys_and_args):
        del script
        keys = list(keys_and_args[:numkeys])
        args = list(keys_and_args[numkeys:])
        amount = int(args[0])
        with self._lock:
            values = [self._strings.get(key) for key in keys]
            if any(value is None for value in values):
                return [-1, -1, -1, -1]

            parsed = [int(value or "0") for value in values]
            if any(value < amount for value in parsed):
                return [0, *parsed]

            updated = [value - amount for value in parsed]
            for key, value in zip(keys, updated, strict=True):
                self._strings[key] = str(value)
            return [1, *updated]

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._strings.get(key)

    def incrby(self, key: str, amount: int = 1) -> int:
        with self._lock:
            current = int(self._strings.get(key, "0")) + amount
            self._strings[key] = str(current)
            return current

    def set(self, key: str, value: str, nx: bool = False) -> bool | None:
        with self._lock:
            if nx and key in self._strings:
                return None
            self._strings[key] = value
            return True

    def flush(self) -> None:
        with self._lock:
            self._strings.clear()


@pytest.fixture()
def temporary_postgres() -> str:
    with TemporaryDirectory(prefix="backend-pg-") as temp_dir:
        base_dir = Path(temp_dir)
        data_dir = base_dir / "data"
        log_path = base_dir / "postgres.log"
        socket_dir = base_dir / "socket"
        socket_dir.mkdir(parents=True, exist_ok=True)
        port = 55436

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


def test_postgres_budget_ledger_reconciles_redis_from_durable_rows(
    migrated_postgres: str,
) -> None:
    redis = FakeRedis()
    ledger = PostgresBudgetLedger(
        migrated_postgres,
        redis_client=redis,
        redis_settings=RedisSettings(url="redis://127.0.0.1:6379/0"),
    )
    context = _context()
    caps = BudgetCaps(
        ticket_cap_usd=Decimal("10"),
        daily_team_cap_usd=Decimal("10"),
        monthly_team_cap_usd=Decimal("10"),
    )

    ledger.configure_caps(context, caps)
    reservation = ledger.reserve(context, Decimal("6"))
    ledger.settle(reservation.reservation_id, Decimal("4"))
    orphan = ledger.reserve(context, Decimal("3"))
    ledger.release_orphaned(orphan.reservation_id, "worker_crash")
    redis.flush()

    balance = ledger.reconcile(context)

    assert balance.ticket_remaining_usd == Decimal("6.00")
    assert balance.daily_team_remaining_usd == Decimal("6.00")
    assert balance.monthly_team_remaining_usd == Decimal("6.00")

    with _connect(migrated_postgres) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM budget_reservations) AS reservations,
                (SELECT COUNT(*) FROM budget_charges) AS charges,
                (SELECT COUNT(*) FROM budget_denials) AS denials
            """
        ).fetchone()

    assert counts["reservations"] == 2
    assert counts["charges"] == 1
    assert counts["denials"] == 0


def test_postgres_budget_ledger_concurrent_reservations_do_not_overrun_team_cap(
    migrated_postgres: str,
) -> None:
    redis = FakeRedis()
    caps = BudgetCaps(
        ticket_cap_usd=Decimal("5"),
        daily_team_cap_usd=Decimal("5"),
        monthly_team_cap_usd=Decimal("5"),
    )
    ledger = PostgresBudgetLedger(
        migrated_postgres,
        redis_client=redis,
        redis_settings=RedisSettings(url="redis://127.0.0.1:6379/0"),
    )
    ledger.configure_caps(_context(run_id="run-1", ticket_key="ENG-1"), caps)
    ledger.configure_caps(_context(run_id="run-2", ticket_key="ENG-2"), caps)

    def reserve_once(index: int) -> str:
        context = _context(run_id=f"run-{index}", ticket_key=f"ENG-{index}")
        ledger = PostgresBudgetLedger(
            migrated_postgres,
            redis_client=redis,
            redis_settings=RedisSettings(url="redis://127.0.0.1:6379/0"),
        )
        ledger.configure_caps(context, caps)
        try:
            ledger.reserve(context, Decimal("3"))
        except BudgetExceededError:
            return "denied"
        return "reserved"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve_once, [1, 2]))

    assert results.count("reserved") == 1
    assert results.count("denied") == 1

    with _connect(migrated_postgres) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM budget_reservations WHERE status = 'active') AS reservations,
                (SELECT COUNT(*) FROM budget_denials) AS denials
            """
        ).fetchone()

    assert counts["reservations"] == 1
    assert counts["denials"] == 1


def _context(*, run_id: str = "run-001", ticket_key: str = "ENG-1") -> BudgetContext:
    return BudgetContext(
        tenant_id="tenant-alpha",
        team_id="team-core",
        run_id=run_id,
        ticket_key=ticket_key,
        role="coder",
    )


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def _connect(database_url: str):
    parsed = make_url(database_url)
    return psycopg.connect(
        host=parsed.host,
        port=parsed.port,
        dbname=parsed.database,
        user=parsed.username,
        password=parsed.password,
        row_factory=dict_row,
        autocommit=True,
    )
