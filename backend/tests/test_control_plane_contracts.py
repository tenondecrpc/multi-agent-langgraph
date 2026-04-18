from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from backend.control_plane import (
    ActivationThresholds,
    AgentConfigValidator,
    ComparisonMetrics,
    GraphConfigValidator,
    GraphConfigVersion,
    GraphEdgeConfig,
    GraphNodeConfig,
    InMemoryControlPlaneStore,
    InMemoryHandlerRegistry,
    RouteHandlerRef,
    ShadowModeEvaluator,
    default_agent_configs,
)
from backend.governance import InMemoryModelCatalog, ModelCatalogEntry, RoleTokenPolicy


def build_catalog() -> InMemoryModelCatalog:
    return InMemoryModelCatalog(
        entries=[
            ModelCatalogEntry(
                model_id="gpt-4.1",
                provider_id="openai",
                deployment_profile="connected",
                max_input_tokens=128_000,
                max_output_tokens=16_000,
                default_price_card_id="card-openai-v1",
                supports_tools=True,
                supports_json_mode=True,
                supports_streaming=True,
                allowed_fallback_targets=["llama3.1"],
            ),
            ModelCatalogEntry(
                model_id="llama3.1",
                provider_id="ollama",
                deployment_profile="connected",
                max_input_tokens=32_000,
                max_output_tokens=8_000,
                default_price_card_id="card-ollama-v1",
                supports_tools=True,
                supports_json_mode=True,
                supports_streaming=False,
            ),
        ],
        role_token_policies=[
            RoleTokenPolicy(role="planner", max_input_tokens=8_000, max_output_tokens=2_000),
            RoleTokenPolicy(role="coder", max_input_tokens=12_000, max_output_tokens=4_000),
            RoleTokenPolicy(role="tester", max_input_tokens=12_000, max_output_tokens=4_000),
            RoleTokenPolicy(role="reviewer", max_input_tokens=10_000, max_output_tokens=3_000),
            RoleTokenPolicy(role="pr_creator", max_input_tokens=6_000, max_output_tokens=2_000),
        ],
    )


def build_handler_refs() -> list[RouteHandlerRef]:
    return [
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
    ]


def build_valid_graph(config_version_id: str) -> GraphConfigVersion:
    return GraphConfigVersion(
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
        route_handlers=build_handler_refs(),
        invariant_profile="ticket_to_pr_v1",
        created_by="admin",
        created_at=datetime.now(tz=UTC),
    )


def test_graph_validator_rejects_compiling_graph_that_skips_required_guards() -> None:
    graph = build_valid_graph("graph-v1")
    graph.graph_nodes = [
        node
        for node in graph.graph_nodes
        if node.node_id not in {"reviewer", "pre_pr_sync"}
    ]
    graph.graph_edges = [
        edge
        for edge in graph.graph_edges
        if edge.source not in {"tester", "reviewer", "pre_pr_sync"}
        and edge.target not in {"reviewer", "pre_pr_sync"}
    ]
    graph.graph_edges.append(
        GraphEdgeConfig(source="tester", target="pr_creator", transition="success")
    )
    validator = GraphConfigValidator(
        handler_registry=InMemoryHandlerRegistry(build_handler_refs())
    )

    result = validator.validate(
        graph,
        registered_escalation_sinks={"missing_or_failing_required_tests"},
    )

    assert result.compiles is True
    assert any("reviewer" in error for error in result.invariant_errors)
    assert any("pre_pr_sync" in error for error in result.invariant_errors)


def test_agent_validation_and_dry_run_respect_role_boundaries() -> None:
    validator = AgentConfigValidator(
        model_catalog=build_catalog(),
        deployment_profile="connected",
    )
    valid_config = next(
        config for config in default_agent_configs() if config.agent_role == "coder"
    )
    invalid_config = valid_config.model_copy(
        update={"allowed_tools": [*valid_config.allowed_tools, "cross_tenant_admin"]}
    )

    assert validator.validate(valid_config).valid is True
    assert validator.validate(invalid_config).valid is False
    assert validator.dry_run(
        valid_config,
        requested_tools=["repo_write", "local_test"],
    ).allowed is True
    assert validator.dry_run(
        valid_config,
        requested_tools=["repo_write", "manage_config"],
    ).blocked_tools == ["manage_config"]


def test_shadow_mode_uses_defense_in_depth_and_blocks_regressions() -> None:
    evaluator = ShadowModeEvaluator()
    isolation = evaluator.build_isolation_profile("graph-v2")
    reduced_isolation = isolation.model_copy(update={"runtime_shadow_flag": False})

    report = evaluator.compare(
        candidate_version_id="graph-v2",
        active_version_id="snapshot-v1",
        metrics=ComparisonMetrics(
            baseline_success_rate=0.96,
            candidate_success_rate=0.82,
            baseline_cost_usd=Decimal("10.00"),
            candidate_cost_usd=Decimal("13.00"),
            safety_regressions=["forbidden_path_attempt"],
        ),
        thresholds=ActivationThresholds(
            minimum_candidate_success_rate=0.90,
            max_cost_delta_usd=Decimal("1.00"),
        ),
    )

    assert isolation.blocks_write_side_effects() is True
    assert reduced_isolation.blocks_write_side_effects() is True
    assert report.blocked is True
    assert "candidate_introduced_safety_regressions" in report.blocking_reasons


def test_config_versioning_activation_and_rollback_keep_pinned_snapshots() -> None:
    store = InMemoryControlPlaneStore()
    graph_v1 = store.create_graph_version(
        payload=build_valid_graph("graph-v1").model_dump(mode="json"),
        actor="admin",
        rationale="initial rollout",
    )
    graph_v2 = store.create_graph_version(
        payload=build_valid_graph("graph-v2").model_dump(mode="json"),
        actor="admin",
        rationale="candidate rollout",
    )

    agent_versions_v1 = {
        config.agent_role: store.create_agent_version(
            payload=config.model_dump(mode="json"),
            actor="admin",
            rationale="initial agent defaults",
        ).record_id
        for config in default_agent_configs()
    }
    agent_versions_v2 = {
        config.agent_role: store.create_agent_version(
            payload=config.model_dump(mode="json"),
            actor="admin",
            rationale="updated agent defaults",
        ).record_id
        for config in default_agent_configs()
    }

    shadow_report_ok = ShadowModeEvaluator().compare(
        candidate_version_id=graph_v1.record_id,
        active_version_id="none",
        metrics=ComparisonMetrics(
            baseline_success_rate=0.0,
            candidate_success_rate=0.95,
            baseline_cost_usd=Decimal("0"),
            candidate_cost_usd=Decimal("5.00"),
        ),
        thresholds=ActivationThresholds(
            minimum_candidate_success_rate=0.90,
            max_cost_delta_usd=Decimal("10.00"),
        ),
    )
    snapshot_v1 = store.activate(
        graph_version_id=graph_v1.record_id,
        agent_version_ids=agent_versions_v1,
        actor="admin",
        rationale="activate baseline",
        comparison_report=shadow_report_ok,
    )
    store.pin_run_snapshot("run-a", snapshot_v1.snapshot_id, "active")

    shadow_report_v2 = ShadowModeEvaluator().compare(
        candidate_version_id=graph_v2.record_id,
        active_version_id=snapshot_v1.snapshot_id,
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
    snapshot_v2 = store.activate(
        graph_version_id=graph_v2.record_id,
        agent_version_ids=agent_versions_v2,
        actor="admin",
        rationale="activate candidate",
        comparison_report=shadow_report_v2,
    )
    store.pin_run_snapshot("run-b", snapshot_v2.snapshot_id, "paused")

    rolled_back = store.rollback(
        snapshot_id=snapshot_v1.snapshot_id,
        actor="admin",
        rationale="restore known good snapshot",
    )

    assert store.active_snapshot().snapshot_id == rolled_back.snapshot_id
    assert store.snapshot_for_run("run-a").snapshot_id == snapshot_v1.snapshot_id
    assert store.snapshot_for_run("run-b").snapshot_id == snapshot_v2.snapshot_id
    assert store.cleanup_retired_snapshots() == []

    store.update_run_status("run-a", "completed")
    store.update_run_status("run-b", "completed")

    assert store.cleanup_retired_snapshots() == [snapshot_v2.snapshot_id]
