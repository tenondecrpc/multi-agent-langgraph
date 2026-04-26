from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from sqlalchemy.engine import make_url

from alembic import command
from backend.persistence import MigrationRunner, build_alembic_config, get_current_revision, get_head_revision
from backend.persistence.db import DatabaseSettings, make_sync_database_url


@pytest.fixture()
def temporary_postgres() -> str:
    with TemporaryDirectory(prefix="backend-pg-") as temp_dir:
        base_dir = Path(temp_dir)
        data_dir = base_dir / "data"
        log_path = base_dir / "postgres.log"
        socket_dir = base_dir / "socket"
        socket_dir.mkdir(parents=True, exist_ok=True)
        port = 55432

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


def test_make_sync_database_url_normalizes_asyncpg_urls() -> None:
    assert (
        make_sync_database_url("postgresql+asyncpg://user:pass@localhost:5432/appdb")
        == "postgresql+psycopg://user:pass@localhost:5432/appdb"
    )


def test_migration_runner_honours_air_gapped_skip_switch(temporary_postgres: str) -> None:
    config = build_alembic_config(temporary_postgres)
    command.upgrade(config, "head")

    runner = MigrationRunner(
        DatabaseSettings(
            url=temporary_postgres,
            air_gapped_skip_migrations=True,
        )
    )
    status = runner.ensure_current()

    assert status.state == "skipped"
    assert status.expected_revision == get_head_revision()
    assert status.current_revision == get_head_revision()
    assert status.reason == "air_gapped_preseeded_database"


def test_alembic_upgrade_downgrade_round_trip_restores_seeded_rows(temporary_postgres: str) -> None:
    config = build_alembic_config(temporary_postgres)
    command.upgrade(config, "head")

    expected_revision = get_head_revision()
    assert get_current_revision(temporary_postgres) == expected_revision

    seeded_rows = _seed_rows(temporary_postgres)

    with _connect(temporary_postgres) as connection:
        policies = connection.execute(
            """
            SELECT policyname
            FROM pg_policies
            WHERE schemaname = 'public'
            ORDER BY policyname
            """
        ).fetchall()
    assert [row["policyname"] for row in policies] == [
        "budget_cap_snapshots_tenant_scope",
        "budget_charges_tenant_scope",
        "budget_denials_tenant_scope",
        "budget_reservations_tenant_scope",
        "dead_letter_records_tenant_scope",
        "knowledge_chunks_tenant_scope",
        "knowledge_documents_tenant_scope",
        "knowledge_ingestion_jobs_tenant_scope",
        "metering_facts_default_tenant_scope",
        "metering_facts_tenant_scope",
        "metering_hourly_rollups_tenant_scope",
        "runs_tenant_scope",
        "webhook_idempotency_records_tenant_scope",
    ]

    command.downgrade(config, "base")
    assert get_current_revision(temporary_postgres) is None

    command.upgrade(config, "head")
    assert get_current_revision(temporary_postgres) == expected_revision

    restored_rows = _seed_rows(
        temporary_postgres,
        seeded_rows=seeded_rows,
    )
    assert restored_rows == seeded_rows


def test_internal_rag_pgvector_migration_round_trip(temporary_postgres: str) -> None:
    with _connect(temporary_postgres) as connection:
        available = connection.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') AS available"
        ).fetchone()

    if not available["available"]:
        pytest.skip("pgvector extension is not available in this PostgreSQL installation")

    config = build_alembic_config(temporary_postgres)
    command.upgrade(config, "20260424_0009")

    with _connect(temporary_postgres) as connection:
        objects = connection.execute(
            """
            SELECT
                to_regclass('knowledge_documents') AS documents_table,
                to_regclass('knowledge_chunks') AS chunks_table,
                to_regclass('knowledge_ingestion_jobs') AS jobs_table,
                to_regclass('ix_knowledge_chunks_embedding_hnsw') AS hnsw_index
            """
        ).fetchone()
        vector_extension = connection.execute(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        policies = connection.execute(
            """
            SELECT policyname
            FROM pg_policies
            WHERE tablename IN (
                'knowledge_documents',
                'knowledge_chunks',
                'knowledge_ingestion_jobs'
            )
            ORDER BY policyname
            """
        ).fetchall()

    assert dict(objects) == {
        "documents_table": "knowledge_documents",
        "chunks_table": "knowledge_chunks",
        "jobs_table": "knowledge_ingestion_jobs",
        "hnsw_index": "ix_knowledge_chunks_embedding_hnsw",
    }
    assert vector_extension["extname"] == "vector"
    assert [row["policyname"] for row in policies] == [
        "knowledge_chunks_tenant_scope",
        "knowledge_documents_tenant_scope",
        "knowledge_ingestion_jobs_tenant_scope",
    ]

    command.downgrade(config, "20260422_0008")

    with _connect(temporary_postgres) as connection:
        removed_objects = connection.execute(
            """
            SELECT
                to_regclass('knowledge_documents') AS documents_table,
                to_regclass('knowledge_chunks') AS chunks_table,
                to_regclass('knowledge_ingestion_jobs') AS jobs_table
            """
        ).fetchone()

    assert dict(removed_objects) == {
        "documents_table": None,
        "chunks_table": None,
        "jobs_table": None,
    }


def _seed_rows(
    database_url: str,
    *,
    seeded_rows: dict[str, dict[str, object]] | None = None,
) -> dict[str, dict[str, object]]:
    seeded_rows = seeded_rows or {}

    run_row = seeded_rows.get("run") or {
        "run_id": "run-001",
        "thread_id": "tenant-alpha:ENG-1:thread-001",
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "repo_id": "repo-dev-squad",
        "ticket_key": "ENG-1",
        "status": "paused",
        "current_node": "tester",
        "paused_at_node": "tester",
        "escalation_reason": "missing_or_failing_required_tests",
        "escalation_sink": "ops://quality",
        "config_snapshot_id": "snapshot-v1",
        "graph_profile_id": "ticket_to_pr_v1",
        "catalog_version": "catalog-v1",
        "state_schema_version": "1",
        "artifact_hashes": {"feature_spec": "abc123"},
        "run_payload": {"pr_created": False, "tests_passed": False},
    }
    webhook_row = seeded_rows.get("webhook") or {
        "source": "jira",
        "delivery_id": "evt-001",
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "endpoint": "/api/v1/webhooks/jira",
        "hmac_digest": "deadbeef",
        "disposition_status": "accepted",
    }
    graph_version_row = seeded_rows.get("graph_version") or {
        "record_id": "graph-001",
        "version_number": 1,
        "created_by": "admin",
        "rationale": "initial graph",
        "payload": {"config_version_id": "graph-001", "profile_id": "ticket-to-pr"},
    }
    agent_version_row = seeded_rows.get("agent_version") or {
        "record_id": "agent-001",
        "version_number": 1,
        "created_by": "admin",
        "rationale": "initial agent",
        "payload": {"agent_role": "coder", "model_id": "gpt-4.1"},
    }
    shadow_report_row = seeded_rows.get("shadow_report") or {
        "report_id": "report-001",
        "candidate_version_id": "graph-001",
        "active_version_id": None,
        "success_rate_delta": "0.0100",
        "cost_delta_usd": "0.5000",
        "safety_regressions": [],
        "blocked": False,
        "blocking_reasons": [],
        "report_payload": {"candidate_version_id": "graph-001", "blocked": False},
    }
    snapshot_row = seeded_rows.get("snapshot") or {
        "snapshot_id": "snapshot-001",
        "graph_version_id": "graph-001",
        "agent_version_ids": {"coder": "agent-001"},
        "shadow_report_id": "report-001",
        "supersedes_snapshot_id": None,
        "created_by": "admin",
        "evidence_summary": "shadow-evidence-passed",
    }
    run_binding_row = seeded_rows.get("run_binding") or {
        "run_id": "run-001",
        "snapshot_id": "snapshot-001",
        "status": "active",
    }
    audit_event_row = seeded_rows.get("audit_event") or {
        "event_id": "audit-001",
        "action": "activate",
        "actor": "admin",
        "rationale": "activate baseline",
        "target_id": "snapshot-001",
        "evidence_summary": "shadow-evidence-passed",
    }
    dead_letter_row = seeded_rows.get("dead_letter") or {
        "job_id": "job-001",
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "run_id": "run-001",
        "queue_name": "ticket-runs",
        "worker_id": "worker-1",
        "failure_reason": "retry_budget_exhausted",
        "checkpoint_ref": "checkpoint-001",
    }
    budget_cap_row = seeded_rows.get("budget_cap") or {
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "run_id": "run-001",
        "ticket_key": "ENG-1",
        "role": "coder",
        "ticket_cap_usd": "10.000000",
        "daily_team_cap_usd": "20.000000",
        "monthly_team_cap_usd": "30.000000",
    }
    budget_reservation_row = seeded_rows.get("budget_reservation") or {
        "reservation_id": "reservation-001",
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "run_id": "run-001",
        "ticket_key": "ENG-1",
        "role": "coder",
        "reserved_amount_usd": "4.000000",
        "ticket_cap_usd": "10.000000",
        "daily_team_cap_usd": "20.000000",
        "monthly_team_cap_usd": "30.000000",
        "ticket_cap_remaining_usd": "6.000000",
        "daily_team_cap_remaining_usd": "16.000000",
        "monthly_team_cap_remaining_usd": "26.000000",
        "status": "active",
        "release_reason": None,
        "released_amount_usd": None,
    }
    budget_charge_row = seeded_rows.get("budget_charge") or {
        "reservation_id": "reservation-001",
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "run_id": "run-001",
        "estimated_cost_usd": "4.000000",
        "actual_cost_usd": "3.000000",
        "refunded_amount_usd": "1.000000",
    }
    budget_denial_row = seeded_rows.get("budget_denial") or {
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "run_id": "run-001",
        "ticket_key": "ENG-1",
        "role": "coder",
        "requested_amount_usd": "9.000000",
        "ticket_cap_usd": "10.000000",
        "daily_team_cap_usd": "20.000000",
        "monthly_team_cap_usd": "30.000000",
        "denial_reason": "budget_exhausted",
        "evidence_summary": "remaining caps exhausted",
    }
    metering_fact_row = seeded_rows.get("metering_fact") or {
        "usage_id": "usage-001",
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "run_id": "run-001",
        "ticket_key": "ENG-1",
        "role": "coder",
        "provider_id": "openai",
        "model_id": "gpt-4.1",
        "deployment_profile": "connected",
        "fallback_used": False,
        "input_tokens": 100,
        "output_tokens": 40,
        "cached_tokens": 0,
        "latency_ms": 250,
        "request_count": 1,
        "reservation_id": "reservation-001",
        "estimated_cost_usd": "0.250000",
        "actual_cost_usd": "0.200000",
        "rate_card_id": "card-openai-v1",
        "trace_id": "trace-001",
        "span_id": "span-001",
        "started_at": "2026-04-18T12:05:00+00:00",
        "completed_at": "2026-04-18T12:06:00+00:00",
        "status": "succeeded",
    }
    metering_rollup_row = seeded_rows.get("metering_rollup") or {
        "rollup_id": "2026-04-18T12:00:00+00:00:team-core:coder:openai:gpt-4.1:card-openai-v1",
        "bucket_start": "2026-04-18T12:00:00+00:00",
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "role": "coder",
        "provider_id": "openai",
        "model_id": "gpt-4.1",
        "rate_card_id": "card-openai-v1",
        "request_count": 1,
        "total_input_tokens": 100,
        "total_output_tokens": 40,
        "total_actual_cost_usd": "0.200000",
        "usage_ids": ["usage-001"],
        "sealed": False,
    }

    with _connect(database_url) as connection:
        connection.execute(
            """
            TRUNCATE TABLE
                audit_events,
                run_snapshot_bindings,
                control_plane_state,
                snapshots,
                shadow_reports,
                agent_versions,
                graph_versions,
                metering_hourly_rollups,
                metering_facts,
                budget_charges,
                budget_denials,
                budget_reservations,
                budget_cap_snapshots,
                dead_letter_records,
                webhook_idempotency_records,
                runs
            RESTART IDENTITY CASCADE
            """
        )
        connection.execute(
            """
            INSERT INTO runs (
                run_id,
                thread_id,
                tenant_id,
                team_id,
                repo_id,
                ticket_key,
                status,
                current_node,
                paused_at_node,
                escalation_reason,
                escalation_sink,
                config_snapshot_id,
                graph_profile_id,
                catalog_version,
                state_schema_version,
                artifact_hashes,
                run_payload
            ) VALUES (
                %(run_id)s,
                %(thread_id)s,
                %(tenant_id)s,
                %(team_id)s,
                %(repo_id)s,
                %(ticket_key)s,
                %(status)s,
                %(current_node)s,
                %(paused_at_node)s,
                %(escalation_reason)s,
                %(escalation_sink)s,
                %(config_snapshot_id)s,
                %(graph_profile_id)s,
                %(catalog_version)s,
                %(state_schema_version)s,
                %(artifact_hashes)s,
                %(run_payload)s
            )
            """,
            {
                **run_row,
                "artifact_hashes": Jsonb(run_row["artifact_hashes"]),
                "run_payload": Jsonb(run_row["run_payload"]),
            },
        )
        connection.execute(
            """
            INSERT INTO webhook_idempotency_records (
                source,
                delivery_id,
                tenant_id,
                team_id,
                endpoint,
                hmac_digest,
                disposition_status
            ) VALUES (
                %(source)s,
                %(delivery_id)s,
                %(tenant_id)s,
                %(team_id)s,
                %(endpoint)s,
                %(hmac_digest)s,
                %(disposition_status)s
            )
            """,
            webhook_row,
        )
        connection.execute(
            """
            INSERT INTO budget_cap_snapshots (
                tenant_id,
                team_id,
                run_id,
                ticket_key,
                role,
                ticket_cap_usd,
                daily_team_cap_usd,
                monthly_team_cap_usd
            ) VALUES (
                %(tenant_id)s,
                %(team_id)s,
                %(run_id)s,
                %(ticket_key)s,
                %(role)s,
                %(ticket_cap_usd)s,
                %(daily_team_cap_usd)s,
                %(monthly_team_cap_usd)s
            )
            """,
            budget_cap_row,
        )
        connection.execute(
            """
            INSERT INTO budget_reservations (
                reservation_id,
                tenant_id,
                team_id,
                run_id,
                ticket_key,
                role,
                reserved_amount_usd,
                ticket_cap_usd,
                daily_team_cap_usd,
                monthly_team_cap_usd,
                ticket_cap_remaining_usd,
                daily_team_cap_remaining_usd,
                monthly_team_cap_remaining_usd,
                status,
                release_reason,
                released_amount_usd
            ) VALUES (
                %(reservation_id)s,
                %(tenant_id)s,
                %(team_id)s,
                %(run_id)s,
                %(ticket_key)s,
                %(role)s,
                %(reserved_amount_usd)s,
                %(ticket_cap_usd)s,
                %(daily_team_cap_usd)s,
                %(monthly_team_cap_usd)s,
                %(ticket_cap_remaining_usd)s,
                %(daily_team_cap_remaining_usd)s,
                %(monthly_team_cap_remaining_usd)s,
                %(status)s,
                %(release_reason)s,
                %(released_amount_usd)s
            )
            """,
            budget_reservation_row,
        )
        connection.execute(
            """
            INSERT INTO budget_charges (
                reservation_id,
                tenant_id,
                team_id,
                run_id,
                estimated_cost_usd,
                actual_cost_usd,
                refunded_amount_usd
            ) VALUES (
                %(reservation_id)s,
                %(tenant_id)s,
                %(team_id)s,
                %(run_id)s,
                %(estimated_cost_usd)s,
                %(actual_cost_usd)s,
                %(refunded_amount_usd)s
            )
            """,
            budget_charge_row,
        )
        connection.execute(
            """
            INSERT INTO budget_denials (
                tenant_id,
                team_id,
                run_id,
                ticket_key,
                role,
                requested_amount_usd,
                ticket_cap_usd,
                daily_team_cap_usd,
                monthly_team_cap_usd,
                denial_reason,
                evidence_summary
            ) VALUES (
                %(tenant_id)s,
                %(team_id)s,
                %(run_id)s,
                %(ticket_key)s,
                %(role)s,
                %(requested_amount_usd)s,
                %(ticket_cap_usd)s,
                %(daily_team_cap_usd)s,
                %(monthly_team_cap_usd)s,
                %(denial_reason)s,
                %(evidence_summary)s
            )
            """,
            budget_denial_row,
        )
        connection.execute(
            """
            INSERT INTO metering_facts (
                usage_id,
                tenant_id,
                team_id,
                run_id,
                ticket_key,
                role,
                provider_id,
                model_id,
                deployment_profile,
                fallback_used,
                input_tokens,
                output_tokens,
                cached_tokens,
                latency_ms,
                request_count,
                reservation_id,
                estimated_cost_usd,
                actual_cost_usd,
                rate_card_id,
                trace_id,
                span_id,
                started_at,
                completed_at,
                status
            ) VALUES (
                %(usage_id)s,
                %(tenant_id)s,
                %(team_id)s,
                %(run_id)s,
                %(ticket_key)s,
                %(role)s,
                %(provider_id)s,
                %(model_id)s,
                %(deployment_profile)s,
                %(fallback_used)s,
                %(input_tokens)s,
                %(output_tokens)s,
                %(cached_tokens)s,
                %(latency_ms)s,
                %(request_count)s,
                %(reservation_id)s,
                %(estimated_cost_usd)s,
                %(actual_cost_usd)s,
                %(rate_card_id)s,
                %(trace_id)s,
                %(span_id)s,
                %(started_at)s,
                %(completed_at)s,
                %(status)s
            )
            """,
            metering_fact_row,
        )
        connection.execute(
            """
            INSERT INTO metering_hourly_rollups (
                rollup_id,
                bucket_start,
                tenant_id,
                team_id,
                role,
                provider_id,
                model_id,
                rate_card_id,
                request_count,
                total_input_tokens,
                total_output_tokens,
                total_actual_cost_usd,
                usage_ids,
                sealed
            ) VALUES (
                %(rollup_id)s,
                %(bucket_start)s,
                %(tenant_id)s,
                %(team_id)s,
                %(role)s,
                %(provider_id)s,
                %(model_id)s,
                %(rate_card_id)s,
                %(request_count)s,
                %(total_input_tokens)s,
                %(total_output_tokens)s,
                %(total_actual_cost_usd)s,
                %(usage_ids)s,
                %(sealed)s
            )
            """,
            {
                **metering_rollup_row,
                "usage_ids": Jsonb(metering_rollup_row["usage_ids"]),
            },
        )
        connection.execute(
            """
            INSERT INTO graph_versions (
                record_id,
                version_number,
                created_by,
                rationale,
                payload
            ) VALUES (
                %(record_id)s,
                %(version_number)s,
                %(created_by)s,
                %(rationale)s,
                %(payload)s
            )
            """,
            {
                **graph_version_row,
                "payload": Jsonb(graph_version_row["payload"]),
            },
        )
        connection.execute(
            """
            INSERT INTO agent_versions (
                record_id,
                version_number,
                created_by,
                rationale,
                payload
            ) VALUES (
                %(record_id)s,
                %(version_number)s,
                %(created_by)s,
                %(rationale)s,
                %(payload)s
            )
            """,
            {
                **agent_version_row,
                "payload": Jsonb(agent_version_row["payload"]),
            },
        )
        connection.execute(
            """
            INSERT INTO shadow_reports (
                report_id,
                candidate_version_id,
                active_version_id,
                success_rate_delta,
                cost_delta_usd,
                safety_regressions,
                blocked,
                blocking_reasons,
                report_payload
            ) VALUES (
                %(report_id)s,
                %(candidate_version_id)s,
                %(active_version_id)s,
                %(success_rate_delta)s,
                %(cost_delta_usd)s,
                %(safety_regressions)s,
                %(blocked)s,
                %(blocking_reasons)s,
                %(report_payload)s
            )
            """,
            {
                **shadow_report_row,
                "safety_regressions": Jsonb(shadow_report_row["safety_regressions"]),
                "blocking_reasons": Jsonb(shadow_report_row["blocking_reasons"]),
                "report_payload": Jsonb(shadow_report_row["report_payload"]),
            },
        )
        connection.execute(
            """
            INSERT INTO snapshots (
                snapshot_id,
                graph_version_id,
                agent_version_ids,
                shadow_report_id,
                supersedes_snapshot_id,
                created_by,
                evidence_summary
            ) VALUES (
                %(snapshot_id)s,
                %(graph_version_id)s,
                %(agent_version_ids)s,
                %(shadow_report_id)s,
                %(supersedes_snapshot_id)s,
                %(created_by)s,
                %(evidence_summary)s
            )
            """,
            {
                **snapshot_row,
                "agent_version_ids": Jsonb(snapshot_row["agent_version_ids"]),
            },
        )
        connection.execute(
            """
            INSERT INTO control_plane_state (
                state_key,
                active_snapshot_id,
                revision
            ) VALUES (
                'global',
                %(active_snapshot_id)s,
                1
            )
            """,
            {"active_snapshot_id": snapshot_row["snapshot_id"]},
        )
        connection.execute(
            """
            INSERT INTO run_snapshot_bindings (
                run_id,
                snapshot_id,
                status
            ) VALUES (
                %(run_id)s,
                %(snapshot_id)s,
                %(status)s
            )
            """,
            run_binding_row,
        )
        connection.execute(
            """
            INSERT INTO audit_events (
                event_id,
                action,
                actor,
                rationale,
                target_id,
                evidence_summary
            ) VALUES (
                %(event_id)s,
                %(action)s,
                %(actor)s,
                %(rationale)s,
                %(target_id)s,
                %(evidence_summary)s
            )
            """,
            audit_event_row,
        )
        connection.execute(
            """
            INSERT INTO dead_letter_records (
                job_id,
                tenant_id,
                team_id,
                run_id,
                queue_name,
                worker_id,
                failure_reason,
                checkpoint_ref
            ) VALUES (
                %(job_id)s,
                %(tenant_id)s,
                %(team_id)s,
                %(run_id)s,
                %(queue_name)s,
                %(worker_id)s,
                %(failure_reason)s,
                %(checkpoint_ref)s
            )
            """,
            dead_letter_row,
        )
        fetched_run = connection.execute(
            """
            SELECT
                run_id,
                thread_id,
                tenant_id,
                team_id,
                repo_id,
                ticket_key,
                status,
                current_node,
                paused_at_node,
                escalation_reason,
                escalation_sink,
                config_snapshot_id,
                graph_profile_id,
                catalog_version,
                state_schema_version,
                artifact_hashes,
                run_payload
            FROM runs
            """
        ).fetchone()
        fetched_webhook = connection.execute(
            """
            SELECT
                source,
                delivery_id,
                tenant_id,
                team_id,
                endpoint,
                hmac_digest,
                disposition_status
            FROM webhook_idempotency_records
            """
        ).fetchone()
        fetched_graph_version = connection.execute(
            """
            SELECT
                record_id,
                version_number,
                created_by,
                rationale,
                payload
            FROM graph_versions
            """
        ).fetchone()
        fetched_agent_version = connection.execute(
            """
            SELECT
                record_id,
                version_number,
                created_by,
                rationale,
                payload
            FROM agent_versions
            """
        ).fetchone()
        fetched_budget_cap = connection.execute(
            """
            SELECT
                tenant_id,
                team_id,
                run_id,
                ticket_key,
                role,
                ticket_cap_usd::text AS ticket_cap_usd,
                daily_team_cap_usd::text AS daily_team_cap_usd,
                monthly_team_cap_usd::text AS monthly_team_cap_usd
            FROM budget_cap_snapshots
            """
        ).fetchone()
        fetched_budget_reservation = connection.execute(
            """
            SELECT
                reservation_id,
                tenant_id,
                team_id,
                run_id,
                ticket_key,
                role,
                reserved_amount_usd::text AS reserved_amount_usd,
                ticket_cap_usd::text AS ticket_cap_usd,
                daily_team_cap_usd::text AS daily_team_cap_usd,
                monthly_team_cap_usd::text AS monthly_team_cap_usd,
                ticket_cap_remaining_usd::text AS ticket_cap_remaining_usd,
                daily_team_cap_remaining_usd::text AS daily_team_cap_remaining_usd,
                monthly_team_cap_remaining_usd::text AS monthly_team_cap_remaining_usd,
                status,
                release_reason,
                released_amount_usd::text AS released_amount_usd
            FROM budget_reservations
            """
        ).fetchone()
        fetched_budget_charge = connection.execute(
            """
            SELECT
                reservation_id,
                tenant_id,
                team_id,
                run_id,
                estimated_cost_usd::text AS estimated_cost_usd,
                actual_cost_usd::text AS actual_cost_usd,
                refunded_amount_usd::text AS refunded_amount_usd
            FROM budget_charges
            """
        ).fetchone()
        fetched_budget_denial = connection.execute(
            """
            SELECT
                tenant_id,
                team_id,
                run_id,
                ticket_key,
                role,
                requested_amount_usd::text AS requested_amount_usd,
                ticket_cap_usd::text AS ticket_cap_usd,
                daily_team_cap_usd::text AS daily_team_cap_usd,
                monthly_team_cap_usd::text AS monthly_team_cap_usd,
                denial_reason,
                evidence_summary
            FROM budget_denials
            """
        ).fetchone()
        fetched_metering_fact = connection.execute(
            """
            SELECT
                usage_id,
                tenant_id,
                team_id,
                run_id,
                ticket_key,
                role,
                provider_id,
                model_id,
                deployment_profile,
                fallback_used,
                input_tokens,
                output_tokens,
                cached_tokens,
                latency_ms,
                request_count,
                reservation_id,
                estimated_cost_usd::text AS estimated_cost_usd,
                actual_cost_usd::text AS actual_cost_usd,
                rate_card_id,
                trace_id,
                span_id,
                started_at::text AS started_at,
                completed_at::text AS completed_at,
                status
            FROM metering_facts
            """
        ).fetchone()
        fetched_metering_rollup = connection.execute(
            """
            SELECT
                rollup_id,
                bucket_start::text AS bucket_start,
                tenant_id,
                team_id,
                role,
                provider_id,
                model_id,
                rate_card_id,
                request_count,
                total_input_tokens,
                total_output_tokens,
                total_actual_cost_usd::text AS total_actual_cost_usd,
                usage_ids,
                sealed
            FROM metering_hourly_rollups
            """
        ).fetchone()
        fetched_shadow_report = connection.execute(
            """
            SELECT
                report_id,
                candidate_version_id,
                active_version_id,
                success_rate_delta::text AS success_rate_delta,
                cost_delta_usd::text AS cost_delta_usd,
                safety_regressions,
                blocked,
                blocking_reasons,
                report_payload
            FROM shadow_reports
            """
        ).fetchone()
        fetched_snapshot = connection.execute(
            """
            SELECT
                snapshot_id,
                graph_version_id,
                agent_version_ids,
                shadow_report_id,
                supersedes_snapshot_id,
                created_by,
                evidence_summary
            FROM snapshots
            """
        ).fetchone()
        fetched_run_binding = connection.execute(
            """
            SELECT
                run_id,
                snapshot_id,
                status
            FROM run_snapshot_bindings
            """
        ).fetchone()
        fetched_audit_event = connection.execute(
            """
            SELECT
                event_id,
                action,
                actor,
                rationale,
                target_id,
                evidence_summary
            FROM audit_events
            """
        ).fetchone()
        fetched_dead_letter = connection.execute(
            """
            SELECT
                job_id,
                tenant_id,
                team_id,
                run_id,
                queue_name,
                worker_id,
                failure_reason,
                checkpoint_ref
            FROM dead_letter_records
            """
        ).fetchone()

    return {
        "run": dict(fetched_run),
        "webhook": dict(fetched_webhook),
        "budget_cap": dict(fetched_budget_cap),
        "budget_reservation": dict(fetched_budget_reservation),
        "budget_charge": dict(fetched_budget_charge),
        "budget_denial": dict(fetched_budget_denial),
        "metering_fact": dict(fetched_metering_fact),
        "metering_rollup": dict(fetched_metering_rollup),
        "graph_version": dict(fetched_graph_version),
        "agent_version": dict(fetched_agent_version),
        "shadow_report": dict(fetched_shadow_report),
        "snapshot": dict(fetched_snapshot),
        "run_binding": dict(fetched_run_binding),
        "audit_event": dict(fetched_audit_event),
        "dead_letter": dict(fetched_dead_letter),
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
    subprocess.run(command_args, check=True, capture_output=True, text=True)
