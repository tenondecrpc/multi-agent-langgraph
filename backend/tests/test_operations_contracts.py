from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.operations import (
    BurnRateAlertPolicy,
    CoveragePolicy,
    CoverageWaiver,
    DashboardDefinition,
    DataCategory,
    ErrorBudgetState,
    IncidentRecord,
    IncidentSeverity,
    LogEvent,
    MigrationPlan,
    ObservabilityCatalog,
    PipelineStage,
    QualityGateService,
    QualitySuiteDefinition,
    RecoveryObjective,
    ReleasePolicy,
    ReplicaStrategy,
    ResiliencePlanner,
    RestoreDrillResult,
    RetentionPolicy,
    RetentionService,
    RollbackDrillResult,
    RolloutAnalysis,
    RunbookReference,
    SliDefinition,
    SliEvaluator,
    SliObservation,
    StatusUpdate,
    StoredRecord,
)


def test_observability_catalog_requires_runbooks_for_pager_incidents() -> None:
    catalog = ObservabilityCatalog()
    catalog.emit_log(
        LogEvent(
            level="info",
            service="backend",
            component="api",
            tenant_id="tenant-alpha",
            team_id="team-core",
            run_id="run-101",
            trace_id="trace-1",
            event_type="run_updated",
            message="Run moved to reviewer",
        )
    )
    catalog.register_dashboard(
        DashboardDefinition(
            dashboard_id="queue-health",
            title="Queue Health",
            panels=["ingress", "workers", "dlq"],
        )
    )
    catalog.register_runbook(
        RunbookReference(
            alert_name="api-burn-rate",
            runbook_id="runbook-api-burn-rate",
            pager_worthy=True,
        )
    )
    incident = IncidentRecord(
        incident_id="inc-1",
        severity=IncidentSeverity.SEV1,
        component="api",
        summary="Ticket intake unavailable",
        runbook_id="runbook-api-burn-rate",
    )
    catalog.record_incident(incident)
    catalog.publish_status_update(
        "inc-1",
        StatusUpdate(
            component="ticket-intake",
            status="degraded",
            message="Webhook intake is delayed for some tenants.",
        ),
    )

    assert catalog.logs[0].tenant_id == "tenant-alpha"
    assert catalog.dashboards["queue-health"].panels == ["ingress", "workers", "dlq"]
    assert catalog.incidents["inc-1"].public_updates[0].component == "ticket-intake"


def test_sli_exclusions_and_burn_rate_drive_error_budget_policy() -> None:
    evaluator = SliEvaluator()
    definition = SliDefinition(
        sli_id="api-availability",
        objective_percent=Decimal("99.0"),
        measurement_window="30d",
        numerator_query="success_count",
        denominator_query="request_count",
        exclusion_query="invalid_auth OR stale_webhook OR rate_limited",
    )
    evaluation = evaluator.evaluate(
        definition,
        SliObservation(total_events=1_000, successful_events=985, excluded_events=10),
    )
    report = evaluator.error_budget_report(definition, evaluation)
    burn_decision = evaluator.evaluate_burn_rate(
        BurnRateAlertPolicy(
            sli_id="api-availability",
            short_window="5m",
            long_window="1h",
            warning_burn_rate=Decimal("1.0"),
            critical_burn_rate=Decimal("2.0"),
        ),
        current_burn_rate=Decimal("2.4"),
    )

    assert evaluation.effective_total == 990
    assert evaluation.availability_percent == Decimal("99.49")
    assert report.state == ErrorBudgetState.LOW
    assert report.release_blocked is False
    assert burn_decision.severity == "critical"


def test_release_policy_blocks_missing_gates_and_rolls_back_on_regression() -> None:
    policy = ReleasePolicy(
        stages=[
            PipelineStage(
                stage_name="source_validation",
                required_gates=["lint", "typecheck", "unit_tests", "policy_scans"],
            )
        ],
        environments=[],
        feature_flags=[],
    )

    stage_result = policy.evaluate_stage(
        "source_validation",
        {"lint": True, "typecheck": False, "unit_tests": True, "policy_scans": False},
    )
    migration_result = policy.validate_migration(
        MigrationPlan(change_id="db-42", expand_first=True, rollback_tested=True)
    )
    rollout_decision = policy.evaluate_rollout(
        RolloutAnalysis(
            error_budget_burn_rate=Decimal("2.2"),
            health_regressed=True,
            kill_switch_engaged=False,
        )
    )

    assert stage_result.passed is False
    assert set(stage_result.missing_gates) == {"typecheck", "policy_scans"}
    assert migration_result.passed is True
    assert rollout_decision.rollback is True


def test_resilience_planner_enforces_dr_objectives_and_ha_controls() -> None:
    planner = ResiliencePlanner()
    assessment = planner.assess_dr(
        RecoveryObjective(rpo_minutes=15, rto_minutes=45),
        restore_drill=RestoreDrillResult(
            drill_id="restore-1",
            restored=True,
            recovery_point_minutes=10,
            recovery_time_minutes=40,
        ),
        rollback_drill=RollbackDrillResult(
            drill_id="rollback-1",
            success=True,
            rollback_time_minutes=12,
        ),
    )
    replica_assessment = planner.validate_replica_strategy(
        ReplicaStrategy(
            primary_count=1,
            replica_count=2,
            anti_affinity=True,
            pod_disruption_budget=True,
            pooled_connections=True,
            safe_read_paths_defined=True,
        )
    )

    assert assessment.continuity_controls_ready is True
    assert replica_assessment.continuity_controls_ready is True


def test_retention_service_keeps_pinned_records_and_audits_cleanup() -> None:
    service = RetentionService()
    now = datetime.now(tz=UTC)
    records = [
        StoredRecord(
            record_id="checkpoint-1",
            category=DataCategory.CHECKPOINTS,
            tenant_id="tenant-alpha",
            created_at=now - timedelta(days=40),
            snapshot_pinned=True,
        ),
        StoredRecord(
            record_id="metering-1",
            category=DataCategory.METERING,
            tenant_id="tenant-alpha",
            created_at=now - timedelta(days=120),
        ),
        StoredRecord(
            record_id="audit-1",
            category=DataCategory.AUDIT,
            tenant_id="tenant-alpha",
            created_at=now - timedelta(days=10),
            incident_open=True,
        ),
    ]
    evidence = service.execute_cleanup(
        tenant_id="tenant-alpha",
        records=records,
        policies={
            DataCategory.CHECKPOINTS: RetentionPolicy(
                category=DataCategory.CHECKPOINTS,
                retention_days=30,
                protect_while_snapshot_pinned=True,
            ),
            DataCategory.METERING: RetentionPolicy(
                category=DataCategory.METERING,
                retention_days=90,
            ),
            DataCategory.AUDIT: RetentionPolicy(
                category=DataCategory.AUDIT,
                retention_days=7,
                protect_while_incident_open=True,
            ),
        },
        now=now,
    )

    assert evidence.deleted_record_ids == ["metering-1"]
    assert evidence.retained_reasons["checkpoint-1"] == "snapshot_pinned"
    assert evidence.retained_reasons["audit-1"] == "incident_open"
    assert service.plan_tenant_deletion("tenant-alpha").cascade_order[0] == DataCategory.DLQ


def test_quality_gates_require_all_layers_and_auditable_coverage_waivers() -> None:
    quality = QualityGateService()
    program_result = quality.validate_quality_program(
        [
            QualitySuiteDefinition(suite_id="unit", layer="unit", required_on_pr=True),
            QualitySuiteDefinition(suite_id="integration", layer="integration", required_on_pr=True),
            QualitySuiteDefinition(suite_id="e2e", layer="e2e", required_on_release=True),
            QualitySuiteDefinition(suite_id="chaos", layer="chaos", required_on_release=True),
            QualitySuiteDefinition(suite_id="fuzz", layer="fuzz", required_on_release=True),
            QualitySuiteDefinition(
                suite_id="prompt",
                layer="prompt_regression",
                required_on_release=True,
            ),
        ]
    )
    coverage_without_waiver = quality.evaluate_coverage(
        CoveragePolicy(
            unit_floor_percent=Decimal("80"),
            integration_floor_percent=Decimal("70"),
        ),
        unit_coverage_percent=Decimal("78"),
        integration_coverage_percent=Decimal("68"),
    )
    coverage_with_waiver = quality.evaluate_coverage(
        CoveragePolicy(
            unit_floor_percent=Decimal("80"),
            integration_floor_percent=Decimal("70"),
        ),
        unit_coverage_percent=Decimal("78"),
        integration_coverage_percent=Decimal("68"),
        waiver=CoverageWaiver(
            waiver_id="waiver-1",
            layer="integration",
            approved_by="release-manager",
            rationale="Temporary migration harness refactor",
        ),
    )

    assert program_result.allowed is True
    assert coverage_without_waiver.allowed is False
    assert coverage_with_waiver.allowed is True
    assert coverage_with_waiver.waiver_used == "waiver-1"
