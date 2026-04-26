from __future__ import annotations

import csv
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus

import psycopg
import pytest
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from alembic import command
from backend.governance.metering import MeteringExportRequest, UsageRecord
from backend.persistence import PostgresMeteringLedger, build_alembic_config


@pytest.fixture()
def temporary_postgres() -> str:
    with TemporaryDirectory(prefix="backend-pg-") as temp_dir:
        base_dir = Path(temp_dir)
        data_dir = base_dir / "data"
        log_path = base_dir / "postgres.log"
        socket_dir = base_dir / "socket"
        socket_dir.mkdir(parents=True, exist_ok=True)
        port = 55437

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


def test_postgres_metering_ledger_builds_idempotent_hourly_rollups(
    migrated_postgres: str,
) -> None:
    ledger = PostgresMeteringLedger(migrated_postgres)
    period_start = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    period_end = datetime(2026, 4, 18, 14, 0, tzinfo=UTC)

    ledger.record_usage(_usage_record("usage-1", completed_at=datetime(2026, 4, 18, 12, 5, tzinfo=UTC)))
    ledger.record_usage(_usage_record("usage-2", completed_at=datetime(2026, 4, 18, 12, 20, tzinfo=UTC)))
    first = ledger.build_hourly_rollups(
        tenant_id="tenant-alpha",
        period_start=period_start,
        period_end=period_end,
    )
    second = ledger.build_hourly_rollups(
        tenant_id="tenant-alpha",
        period_start=period_start,
        period_end=period_end,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].request_count == 2
    assert first[0].total_actual_cost_usd == Decimal("0.400000")

    with _connect(migrated_postgres) as connection:
        count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM metering_hourly_rollups"
        ).fetchone()

    assert count_row["count"] == 1


def test_csv_export_reads_rollups_and_matches_fact_totals(
    migrated_postgres: str,
) -> None:
    ledger = PostgresMeteringLedger(migrated_postgres)
    period_start = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    period_end = datetime(2026, 4, 18, 14, 0, tzinfo=UTC)
    usage_one = _usage_record("usage-1", completed_at=datetime(2026, 4, 18, 12, 5, tzinfo=UTC))
    usage_two = _usage_record("usage-2", completed_at=datetime(2026, 4, 18, 13, 15, tzinfo=UTC))

    ledger.record_usage(usage_one)
    ledger.record_usage(usage_two)
    rollups = ledger.build_hourly_rollups(
        tenant_id="tenant-alpha",
        period_start=period_start,
        period_end=period_end,
    )

    exported = ledger.export(
        MeteringExportRequest(
            tenant_id="tenant-alpha",
            period_start=period_start,
            period_end=period_end,
            format="csv",
        )
    )
    rows = list(csv.DictReader(exported.splitlines()))
    exported_total = sum((Decimal(row["total_actual_cost_usd"]) for row in rows), start=Decimal("0"))
    facts_total = usage_one.actual_cost_usd + usage_two.actual_cost_usd

    assert len(rows) == len(rollups)
    assert exported_total == facts_total


def test_reconciliation_reports_rollup_ids_and_fact_usage_ids(
    migrated_postgres: str,
) -> None:
    ledger = PostgresMeteringLedger(migrated_postgres)
    period_start = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    period_end = datetime(2026, 4, 18, 14, 0, tzinfo=UTC)
    usage = _usage_record("usage-1", completed_at=datetime(2026, 4, 18, 12, 5, tzinfo=UTC))

    ledger.record_usage(usage)
    result = ledger.reconcile(
        tenant_id="tenant-alpha",
        period_start=period_start,
        period_end=period_end,
        provider_reported_total_usd=Decimal("0.200000"),
    )

    assert result.metered_total_usd == Decimal("0.200000")
    assert result.drift_amount_usd == Decimal("0.000000")
    assert result.usage_ids == ["usage-1"]
    assert len(result.rollup_ids) == 1


def _usage_record(usage_id: str, *, completed_at: datetime) -> UsageRecord:
    return UsageRecord(
        usage_id=usage_id,
        tenant_id="tenant-alpha",
        team_id="team-core",
        run_id="run-001",
        ticket_key="ENG-1",
        role="coder",
        provider_id="openai",
        model_id="gpt-4.1",
        deployment_profile="connected",
        fallback_used=False,
        input_tokens=100,
        output_tokens=40,
        cached_tokens=0,
        latency_ms=250,
        request_count=1,
        reservation_id="reservation-001",
        estimated_cost_usd=Decimal("0.250000"),
        actual_cost_usd=Decimal("0.200000"),
        rate_card_id="card-openai-v1",
        trace_id="trace-001",
        span_id="span-001",
        started_at=completed_at.replace(minute=0),
        completed_at=completed_at,
        status="succeeded",
    )


def _connect(database_url: str):
    parsed = make_url(database_url)
    return psycopg.connect(
        host=parsed.query.get("host") or parsed.host,
        port=parsed.query.get("port") or parsed.port,
        dbname=parsed.database,
        user=parsed.username,
        password=parsed.password,
        row_factory=dict_row,
        autocommit=True,
    )


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)
