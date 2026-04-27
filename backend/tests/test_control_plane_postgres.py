from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus

import psycopg
import pytest
from psycopg import errors as psycopg_errors
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from alembic import command
from backend.control_plane import (
    ActivationThresholds,
    ComparisonMetrics,
    ControlPlaneConflictError,
    GraphConfigVersion,
    GraphEdgeConfig,
    GraphNodeConfig,
    RouteHandlerRef,
    ShadowModeEvaluator,
    default_agent_configs,
)
from backend.persistence import (
    PostgresControlPlaneStore,
    SnapshotDrivenHandlerRegistry,
    build_alembic_config,
)


class FakeSnapshotActivationBroadcaster:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self._subscribers: list[callable] = []

    def publish(self, snapshot_id: str) -> None:
        self.messages.append(snapshot_id)
        for subscriber in list(self._subscribers):
            subscriber(snapshot_id)

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)


@pytest.fixture()
def temporary_postgres() -> str:
    with TemporaryDirectory(prefix="backend-pg-") as temp_dir:
        base_dir = Path(temp_dir)
        data_dir = base_dir / "data"
        log_path = base_dir / "postgres.log"
        socket_dir = base_dir / "socket"
        socket_dir.mkdir(parents=True, exist_ok=True)
        port = 55434

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


def test_postgres_control_plane_detects_concurrent_activation_conflicts(
    migrated_postgres: str,
) -> None:
    broadcaster = FakeSnapshotActivationBroadcaster()
    store_a = PostgresControlPlaneStore(migrated_postgres, broadcaster=broadcaster)
    store_b = PostgresControlPlaneStore(migrated_postgres, broadcaster=broadcaster)

    graph_v1 = store_a.create_graph_version(
        payload=_graph_payload("graph-v1", custom_kind="system"),
        actor="admin",
        rationale="baseline graph",
    )
    graph_v2 = store_a.create_graph_version(
        payload=_graph_payload("graph-v2", custom_kind="tenant_configurable"),
        actor="admin",
        rationale="candidate graph",
    )
    graph_v3 = store_a.create_graph_version(
        payload=_graph_payload("graph-v3", custom_kind="tenant_configurable"),
        actor="admin",
        rationale="second candidate graph",
    )
    agent_version_ids = _create_agent_versions(store_a)

    snapshot_v1 = store_a.activate(
        graph_version_id=graph_v1.record_id,
        agent_version_ids=agent_version_ids,
        actor="admin",
        rationale="activate baseline",
        comparison_report=_shadow_report(graph_v1.record_id, active_snapshot_id="none"),
    )

    winning_snapshot = store_a.activate(
        graph_version_id=graph_v2.record_id,
        agent_version_ids=agent_version_ids,
        actor="operator-a",
        rationale="activate candidate A",
        comparison_report=_shadow_report(
            graph_v2.record_id,
            active_snapshot_id=snapshot_v1.snapshot_id,
        ),
    )

    with pytest.raises(ControlPlaneConflictError):
        store_b.activate(
            graph_version_id=graph_v3.record_id,
            agent_version_ids=agent_version_ids,
            actor="operator-b",
            rationale="activate candidate B",
            comparison_report=_shadow_report(
                graph_v3.record_id,
                active_snapshot_id=snapshot_v1.snapshot_id,
            ),
        )

    assert store_a.active_snapshot().snapshot_id == winning_snapshot.snapshot_id

    with _connect(migrated_postgres) as connection:
        activations = connection.execute(
            """
            SELECT actor, target_id
            FROM audit_events
            WHERE action = 'activate'
            ORDER BY created_at
            """
        ).fetchall()

    assert [row["target_id"] for row in activations] == [
        snapshot_v1.snapshot_id,
        winning_snapshot.snapshot_id,
    ]


def test_postgres_control_plane_rollback_keeps_pinned_runs_stable(
    migrated_postgres: str,
) -> None:
    broadcaster = FakeSnapshotActivationBroadcaster()
    store = PostgresControlPlaneStore(migrated_postgres, broadcaster=broadcaster)

    graph_v1 = store.create_graph_version(
        payload=_graph_payload("graph-v1", custom_kind="system"),
        actor="admin",
        rationale="baseline graph",
    )
    graph_v2 = store.create_graph_version(
        payload=_graph_payload("graph-v2", custom_kind="tenant_configurable"),
        actor="admin",
        rationale="candidate graph",
    )
    agent_versions_v1 = _create_agent_versions(store)
    agent_versions_v2 = _create_agent_versions(store)

    snapshot_v1 = store.activate(
        graph_version_id=graph_v1.record_id,
        agent_version_ids=agent_versions_v1,
        actor="admin",
        rationale="activate baseline",
        comparison_report=_shadow_report(graph_v1.record_id, active_snapshot_id="none"),
    )
    _seed_run(migrated_postgres, "run-a")
    store.pin_run_snapshot("run-a", snapshot_v1.snapshot_id, "active")

    snapshot_v2 = store.activate(
        graph_version_id=graph_v2.record_id,
        agent_version_ids=agent_versions_v2,
        actor="admin",
        rationale="activate candidate",
        comparison_report=_shadow_report(
            graph_v2.record_id,
            active_snapshot_id=snapshot_v1.snapshot_id,
        ),
    )
    _seed_run(migrated_postgres, "run-b")
    store.pin_run_snapshot("run-b", snapshot_v2.snapshot_id, "paused")

    rolled_back = store.rollback(
        snapshot_id=snapshot_v1.snapshot_id,
        actor="admin",
        rationale="restore known good snapshot",
        expected_active_snapshot_id=snapshot_v2.snapshot_id,
    )

    assert store.active_snapshot().snapshot_id == rolled_back.snapshot_id
    assert store.snapshot_for_run("run-a").snapshot_id == snapshot_v1.snapshot_id
    assert store.snapshot_for_run("run-b").snapshot_id == snapshot_v2.snapshot_id

    store.update_run_status("run-a", "completed")
    store.update_run_status("run-b", "completed")

    assert store.cleanup_retired_snapshots() == [snapshot_v2.snapshot_id]


def test_snapshot_driven_handler_registry_invalidates_on_activation(
    migrated_postgres: str,
) -> None:
    broadcaster = FakeSnapshotActivationBroadcaster()
    store = PostgresControlPlaneStore(migrated_postgres, broadcaster=broadcaster)
    registry = SnapshotDrivenHandlerRegistry(
        migrated_postgres,
        broadcaster=broadcaster,
        cache_ttl_seconds=60,
    )

    graph_v1 = store.create_graph_version(
        payload=_graph_payload("graph-v1", custom_kind="system"),
        actor="admin",
        rationale="baseline graph",
    )
    graph_v2 = store.create_graph_version(
        payload=_graph_payload("graph-v2", custom_kind="tenant_configurable"),
        actor="admin",
        rationale="candidate graph",
    )
    agent_version_ids = _create_agent_versions(store)

    snapshot_v1 = store.activate(
        graph_version_id=graph_v1.record_id,
        agent_version_ids=agent_version_ids,
        actor="admin",
        rationale="activate baseline",
        comparison_report=_shadow_report(graph_v1.record_id, active_snapshot_id="none"),
    )

    assert registry.resolve("route-special") == "system"

    snapshot_v2 = store.activate(
        graph_version_id=graph_v2.record_id,
        agent_version_ids=agent_version_ids,
        actor="admin",
        rationale="activate candidate",
        comparison_report=_shadow_report(
            graph_v2.record_id,
            active_snapshot_id=snapshot_v1.snapshot_id,
        ),
    )

    assert broadcaster.messages[-1] == snapshot_v2.snapshot_id
    assert registry.resolve("route-special") == "tenant_configurable"


def test_audit_events_are_append_only(migrated_postgres: str) -> None:
    store = PostgresControlPlaneStore(migrated_postgres)
    graph_v1 = store.create_graph_version(
        payload=_graph_payload("graph-v1", custom_kind="system"),
        actor="admin",
        rationale="baseline graph",
    )
    store.activate(
        graph_version_id=graph_v1.record_id,
        agent_version_ids=_create_agent_versions(store),
        actor="admin",
        rationale="activate baseline",
        comparison_report=_shadow_report(graph_v1.record_id, active_snapshot_id="none"),
    )

    with _connect(migrated_postgres) as connection:
        audit_event = connection.execute(
            "SELECT event_id FROM audit_events ORDER BY created_at LIMIT 1"
        ).fetchone()

        with pytest.raises(psycopg_errors.RaiseException):
            connection.execute(
                "UPDATE audit_events SET rationale = 'tampered' WHERE event_id = %(event_id)s",
                {"event_id": audit_event["event_id"]},
            )

        with pytest.raises(psycopg_errors.RaiseException):
            connection.execute(
                "DELETE FROM audit_events WHERE event_id = %(event_id)s",
                {"event_id": audit_event["event_id"]},
            )


def _graph_payload(config_version_id: str, *, custom_kind: str) -> dict[str, object]:
    graph = GraphConfigVersion(
        config_version_id=config_version_id,
        profile_id="ticket-to-pr",
        graph_nodes=[
            GraphNodeConfig(node_id="load_constitution", handler_name="load_constitution", handler_kind="system"),
            GraphNodeConfig(node_id="create_feature_spec", handler_name="create_feature_spec", handler_kind="system"),
            GraphNodeConfig(node_id="clarify", handler_name="clarify", handler_kind="system"),
            GraphNodeConfig(node_id="create_plan", handler_name="create_plan", handler_kind="system"),
            GraphNodeConfig(node_id="create_task_list", handler_name="create_task_list", handler_kind="system"),
            GraphNodeConfig(node_id="readiness_gate", handler_name="readiness_gate", handler_kind="system"),
            GraphNodeConfig(node_id="coder", handler_name="coder", handler_kind="system", writes_repo=True),
            GraphNodeConfig(node_id="tester", handler_name="tester", handler_kind="system"),
            GraphNodeConfig(node_id="reviewer", handler_name="reviewer", handler_kind="system"),
            GraphNodeConfig(node_id="pre_pr_sync", handler_name="pre_pr_sync", handler_kind="system"),
            GraphNodeConfig(node_id="pr_creator", handler_name="pr_creator", handler_kind="system"),
            GraphNodeConfig(node_id="escalate", handler_name="escalate", handler_kind="system", terminal=True),
        ],
        graph_edges=[
            GraphEdgeConfig(source="START", target="load_constitution", transition="success"),
            GraphEdgeConfig(source="load_constitution", target="create_feature_spec", transition="success"),
            GraphEdgeConfig(source="create_feature_spec", target="clarify", transition="success"),
            GraphEdgeConfig(source="clarify", target="create_plan", transition="success"),
            GraphEdgeConfig(source="create_plan", target="create_task_list", transition="success"),
            GraphEdgeConfig(source="create_task_list", target="readiness_gate", transition="success"),
            GraphEdgeConfig(source="readiness_gate", target="coder", transition="success"),
            GraphEdgeConfig(source="coder", target="tester", transition="success"),
            GraphEdgeConfig(source="tester", target="reviewer", transition="success"),
            GraphEdgeConfig(source="reviewer", target="pre_pr_sync", transition="success"),
            GraphEdgeConfig(source="pre_pr_sync", target="pr_creator", transition="success"),
            GraphEdgeConfig(
                source="tester",
                target="escalate",
                transition="escalate",
                escalation_reason="missing_or_failing_required_tests",
            ),
            GraphEdgeConfig(
                source="escalate",
                target="END",
                transition="terminal",
                escalation_reason="missing_or_failing_required_tests",
            ),
        ],
        route_handlers=[
            RouteHandlerRef(handler_name="load_constitution", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="create_feature_spec", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="clarify", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="create_plan", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="create_task_list", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="readiness_gate", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="coder", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="tester", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="reviewer", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="pre_pr_sync", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="pr_creator", handler_version="1", handler_kind="system"),
            RouteHandlerRef(handler_name="escalate", handler_version="1", handler_kind="system"),
            RouteHandlerRef(
                handler_name="route-special",
                handler_version="1",
                handler_kind=custom_kind,  # type: ignore[arg-type]
            ),
        ],
        invariant_profile="ticket_to_pr_v1",
        created_by="admin",
        created_at=datetime.now(tz=UTC),
    )
    return graph.model_dump(mode="json")


def _create_agent_versions(store: PostgresControlPlaneStore) -> dict[str, str]:
    return {
        config.agent_role: store.create_agent_version(
            payload=config.model_dump(mode="json"),
            actor="admin",
            rationale=f"seed {config.agent_role}",
        ).record_id
        for config in default_agent_configs()
    }


def _shadow_report(graph_version_id: str, *, active_snapshot_id: str) -> object:
    return ShadowModeEvaluator().compare(
        candidate_version_id=graph_version_id,
        active_version_id=active_snapshot_id,
        metrics=ComparisonMetrics(
            baseline_success_rate=0.95,
            candidate_success_rate=0.96,
            baseline_cost_usd=Decimal("5.00"),
            candidate_cost_usd=Decimal("5.50"),
        ),
        thresholds=ActivationThresholds(
            minimum_candidate_success_rate=0.90,
            max_cost_delta_usd=Decimal("2.00"),
        ),
    )


def _seed_run(database_url: str, run_id: str) -> None:
    with _connect(database_url) as connection:
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
                config_snapshot_id,
                graph_profile_id,
                catalog_version
            ) VALUES (
                %(run_id)s,
                %(thread_id)s,
                'tenant-alpha',
                'team-core',
                'repo-main',
                'ENG-1',
                'active',
                'planner',
                'config-v1',
                'ticket_to_pr_v1',
                'catalog-v1'
            )
            """,
            {"run_id": run_id, "thread_id": f"tenant-alpha:ENG-1:{run_id}"},
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
    try:
        subprocess.run(command_args, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        pytest.skip(f"ephemeral postgres bootstrap unavailable in this environment: {exc}")
