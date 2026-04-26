from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.governance import (
    BudgetCaps,
    BudgetContext,
    BudgetExceededError,
    InMemoryBudgetLedger,
    InMemoryMeteringLedger,
    InMemoryModelCatalog,
    InMemoryProviderHealthStore,
    MeteringExportRequest,
    ModelCatalogEntry,
    RoleModelAssignment,
    RoleTokenPolicy,
    RuleBasedProviderRouter,
    TokenCap,
    UsageRecord,
)
from backend.runtime import EscalationReason, RuntimeWorkflow


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
            ModelCatalogEntry(
                model_id="opencode-go/kimi-k2.5",
                provider_id="opencode-go",
                deployment_profile="air_gapped",
                max_input_tokens=16_000,
                max_output_tokens=4_000,
                default_price_card_id="card-airgap-v1",
                supports_tools=True,
                supports_json_mode=True,
                supports_streaming=False,
                allowed_fallback_targets=["opencode-go/minimax-m2.7"],
            ),
            ModelCatalogEntry(
                model_id="opencode-go/minimax-m2.7",
                provider_id="opencode-go",
                deployment_profile="air_gapped",
                max_input_tokens=16_000,
                max_output_tokens=4_000,
                default_price_card_id="card-airgap-v1",
                supports_tools=True,
                supports_json_mode=True,
                supports_streaming=False,
            ),
        ],
        role_token_policies=[
            RoleTokenPolicy(
                role="planner",
                max_input_tokens=8_000,
                max_output_tokens=2_000,
            ),
            RoleTokenPolicy(
                role="coder",
                max_input_tokens=12_000,
                max_output_tokens=4_000,
            ),
            RoleTokenPolicy(
                role="tester",
                max_input_tokens=12_000,
                max_output_tokens=4_000,
            ),
            RoleTokenPolicy(
                role="reviewer",
                max_input_tokens=10_000,
                max_output_tokens=3_000,
            ),
            RoleTokenPolicy(
                role="pr_creator",
                max_input_tokens=6_000,
                max_output_tokens=2_000,
            ),
        ],
    )


def build_budget_context() -> BudgetContext:
    return BudgetContext(
        tenant_id="tenant-alpha",
        team_id="team-core",
        run_id="run-123",
        ticket_key="ENG-101",
        role="coder",
    )


def test_provider_router_failover_and_recovery_behaviour() -> None:
    catalog = build_catalog()
    health_store = InMemoryProviderHealthStore(failure_threshold=2, recovery_probe_limit=1)
    router = RuleBasedProviderRouter(
        model_catalog=catalog,
        health_store=health_store,
        role_assignments=[
            RoleModelAssignment(
                role="coder",
                primary_model_id="gpt-4.1",
                fallback_model_id="llama3.1",
            )
        ],
    )
    context = build_budget_context()

    primary = router.select_model(
        role="coder",
        run_id=context.run_id,
        tenant_id=context.tenant_id,
        budget_context=context,
        deployment_profile="connected",
    )
    health_store.record_failure("openai")
    health_store.record_failure("openai")

    fallback = router.select_model(
        role="coder",
        run_id=context.run_id,
        tenant_id=context.tenant_id,
        budget_context=context,
        deployment_profile="connected",
    )
    health_store.move_to_half_open("openai")
    probe = router.select_model(
        role="coder",
        run_id=context.run_id,
        tenant_id=context.tenant_id,
        budget_context=context,
        deployment_profile="connected",
    )
    health_store.record_success("openai")

    recovered = router.select_model(
        role="coder",
        run_id=context.run_id,
        tenant_id=context.tenant_id,
        budget_context=context,
        deployment_profile="connected",
    )

    assert primary.provider_id == "openai"
    assert fallback.provider_id == "ollama"
    assert fallback.fallback_used is True
    assert probe.provider_id == "openai"
    assert recovered.provider_id == "openai"


def test_provider_router_blocks_when_all_providers_are_unavailable() -> None:
    catalog = build_catalog()
    health_store = InMemoryProviderHealthStore(failure_threshold=1)
    router = RuleBasedProviderRouter(
        model_catalog=catalog,
        health_store=health_store,
        role_assignments=[
            RoleModelAssignment(
                role="coder",
                primary_model_id="gpt-4.1",
                fallback_model_id="llama3.1",
            )
        ],
    )
    context = build_budget_context()

    health_store.record_failure("openai")
    health_store.record_failure("ollama")

    with pytest.raises(Exception) as exc_info:
        router.select_model(
            role="coder",
            run_id=context.run_id,
            tenant_id=context.tenant_id,
            budget_context=context,
            deployment_profile="connected",
        )

    assert str(exc_info.value) == EscalationReason.ALL_PROVIDERS_UNAVAILABLE.value


def test_model_catalog_token_caps_and_air_gapped_validation() -> None:
    catalog = build_catalog()
    effective_cap = catalog.effective_token_cap(
        role="coder",
        model_id="gpt-4.1",
        deployment_profile="connected",
        tenant_override=TokenCap(input_tokens=10_000, output_tokens=2_500),
    )

    assert effective_cap.input_tokens == 10_000
    assert effective_cap.output_tokens == 2_500

    with pytest.raises(ValueError):
        catalog.resolve_model("gpt-4.1", "air_gapped")


def test_air_gapped_provider_router_uses_only_opencode_go_models() -> None:
    catalog = build_catalog()
    health_store = InMemoryProviderHealthStore()
    router = RuleBasedProviderRouter(
        model_catalog=catalog,
        health_store=health_store,
        role_assignments=[
            RoleModelAssignment(
                role="coder",
                primary_model_id="opencode-go/kimi-k2.5",
                fallback_model_id="opencode-go/minimax-m2.7",
            )
        ],
    )
    context = build_budget_context()

    primary = router.select_model(
        role="coder",
        run_id=context.run_id,
        tenant_id=context.tenant_id,
        budget_context=context,
        deployment_profile="air_gapped",
    )
    health_store.record_failure("opencode-go")
    health_store.record_failure("opencode-go")

    with pytest.raises(Exception) as exc_info:
        router.select_model(
            role="coder",
            run_id=context.run_id,
            tenant_id=context.tenant_id,
            budget_context=context,
            deployment_profile="air_gapped",
        )

    assert primary.provider_id == "opencode-go"
    assert primary.model_id == "opencode-go/kimi-k2.5"
    assert str(exc_info.value) == EscalationReason.ALL_PROVIDERS_UNAVAILABLE.value


def test_budget_reservations_are_atomic_under_parallel_load() -> None:
    context = build_budget_context()
    ledger = InMemoryBudgetLedger()
    ledger.configure_caps(
        context,
        BudgetCaps(
            ticket_cap_usd=Decimal("10"),
            daily_team_cap_usd=Decimal("10"),
            monthly_team_cap_usd=Decimal("10"),
        ),
    )

    def reserve_once() -> bool:
        try:
            ledger.reserve(context, Decimal("4"))
        except BudgetExceededError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: reserve_once(), range(4)))

    balance = ledger.balance(context)

    assert results.count(True) == 2
    assert results.count(False) == 2
    assert balance.ticket_remaining_usd == Decimal("2")


def test_budget_settlement_and_orphan_recovery_reconcile_reserved_cost() -> None:
    context = build_budget_context()
    ledger = InMemoryBudgetLedger()
    ledger.configure_caps(
        context,
        BudgetCaps(
            ticket_cap_usd=Decimal("10"),
            daily_team_cap_usd=Decimal("10"),
            monthly_team_cap_usd=Decimal("10"),
        ),
    )

    settled = ledger.reserve(context, Decimal("6"))
    orphan = ledger.reserve(context, Decimal("3"))
    ledger.settle(settled.reservation_id, Decimal("4"))
    ledger.release_orphaned(orphan.reservation_id, "worker_crash")

    balance = ledger.balance(context)

    assert ledger.settlements[0].refunded_amount_usd == Decimal("2")
    assert ledger.orphaned_releases[0].reason == "worker_crash"
    assert balance.ticket_remaining_usd == Decimal("6")


def test_metering_rollups_exports_and_reconciliation_are_reproducible() -> None:
    ledger = InMemoryMeteringLedger()
    started_at = datetime(2026, 4, 17, 10, 5, tzinfo=UTC)
    completed_at = started_at + timedelta(seconds=2)
    later_completed_at = started_at + timedelta(minutes=10)

    ledger.record_usage(
        UsageRecord(
            usage_id="usage-1",
            tenant_id="tenant-alpha",
            team_id="team-core",
            run_id="run-123",
            ticket_key="ENG-101",
            role="coder",
            provider_id="openai",
            model_id="gpt-4.1",
            deployment_profile="connected",
            input_tokens=300,
            output_tokens=120,
            latency_ms=1200,
            estimated_cost_usd=Decimal("1.80"),
            actual_cost_usd=Decimal("1.50"),
            rate_card_id="card-openai-v1",
            trace_id="trace-1",
            span_id="span-1",
            started_at=started_at,
            completed_at=completed_at,
        )
    )
    ledger.record_usage(
        UsageRecord(
            usage_id="usage-2",
            tenant_id="tenant-alpha",
            team_id="team-core",
            run_id="run-123",
            ticket_key="ENG-101",
            role="coder",
            provider_id="openai",
            model_id="gpt-4.1",
            deployment_profile="connected",
            fallback_used=True,
            input_tokens=200,
            output_tokens=80,
            latency_ms=900,
            estimated_cost_usd=Decimal("2.70"),
            actual_cost_usd=Decimal("2.50"),
            rate_card_id="card-openai-v1",
            trace_id="trace-2",
            span_id="span-2",
            started_at=started_at,
            completed_at=later_completed_at,
        )
    )

    rollups = ledger.build_hourly_rollups(
        tenant_id="tenant-alpha",
        period_start=started_at - timedelta(minutes=5),
        period_end=started_at + timedelta(hours=1),
    )
    csv_export = ledger.export(
        MeteringExportRequest(
            tenant_id="tenant-alpha",
            period_start=started_at - timedelta(minutes=5),
            period_end=started_at + timedelta(hours=1),
            format="csv",
        )
    )
    reconciliation = ledger.reconcile(
        tenant_id="tenant-alpha",
        period_start=started_at - timedelta(minutes=5),
        period_end=started_at + timedelta(hours=1),
        provider_reported_total_usd=Decimal("4.00"),
    )

    assert len(rollups) == 1
    assert rollups[0].total_actual_cost_usd == Decimal("4.00")
    assert "usage_id,tenant_id,team_id" in csv_export
    assert "usage-1" in csv_export
    assert reconciliation.drift_amount_usd == Decimal("0.00")
    assert reconciliation.usage_ids == ["usage-1", "usage-2"]


def test_metering_export_versions_reconcile_to_same_total() -> None:
    ledger = InMemoryMeteringLedger()
    completed_at = datetime(2026, 4, 17, 10, 5, tzinfo=UTC)
    request_window = {
        "tenant_id": "tenant-alpha",
        "period_start": completed_at - timedelta(minutes=5),
        "period_end": completed_at + timedelta(minutes=5),
        "format": "csv",
    }

    ledger.record_usage(
        UsageRecord(
            usage_id="usage-1",
            tenant_id="tenant-alpha",
            team_id="team-core",
            run_id="run-123",
            ticket_key="ENG-101",
            role="coder",
            provider_id="openai",
            model_id="gpt-4.1",
            deployment_profile="connected",
            input_tokens=300,
            output_tokens=120,
            latency_ms=1200,
            estimated_cost_usd=Decimal("1.80"),
            actual_cost_usd=Decimal("1.50"),
            rate_card_id="card-openai-v1",
            trace_id="trace-1",
            span_id="span-1",
            started_at=completed_at - timedelta(seconds=2),
            completed_at=completed_at,
        )
    )

    v1_export = ledger.export(MeteringExportRequest(**request_window, schema_version="v1"))
    v2_export = ledger.export(MeteringExportRequest(**request_window, schema_version="v2"))
    v1_rows = list(csv.DictReader(v1_export.splitlines()))
    v2_rows = list(csv.DictReader(v2_export.splitlines()))

    assert v2_rows[0]["schema_version"] == "v2"
    assert sum(Decimal(row["actual_cost_usd"]) for row in v1_rows) == Decimal("1.50")
    assert sum(Decimal(row["actual_cost_usd"]) for row in v2_rows) == Decimal("1.50")


def test_runtime_default_sinks_include_llm_governance_reasons() -> None:
    sinks = RuntimeWorkflow.default_escalation_sinks()

    assert sinks[EscalationReason.BUDGET_EXHAUSTED.value] == "ops://budgeting"
    assert sinks[EscalationReason.ALL_PROVIDERS_UNAVAILABLE.value] == "ops://llm-routing"
    assert (
        sinks[EscalationReason.ORPHANED_BUDGET_RESERVATION_DETECTED.value]
        == "ops://budgeting"
    )
