from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.governance.metering import (
    RateCardCreate,
    RateCardUpdate,
    UsageRecord,
)
from backend.persistence.testing.governance import InMemoryMeteringLedger


@pytest.fixture
def now():
    return datetime.now(tz=UTC)


@pytest.fixture
def usage_record(now):
    return UsageRecord(
        usage_id=str(uuid4()),
        tenant_id="tenant-test",
        team_id="team-alpha",
        run_id="run-1",
        ticket_key="PROJ-123",
        role="coder",
        provider_id="openai",
        model_id="gpt-4.1",
        deployment_profile="connected",
        input_tokens=1000,
        output_tokens=500,
        latency_ms=200,
        estimated_cost_usd=Decimal("0.05"),
        actual_cost_usd=Decimal("0.045"),
        rate_card_id="card-openai-v1",
        provider_request_id="req-abc-123",
        trace_id="trace-1",
        span_id="span-1",
        started_at=now - timedelta(minutes=5),
        completed_at=now,
    )


class TestRateCardLifecycle:
    def test_create_rate_card(self, now):
        ledger = InMemoryMeteringLedger()
        data = RateCardCreate(
            provider="openai",
            model="gpt-4.1",
            rate_usd=Decimal("0.00003"),
            effective_from=now,
            created_by="admin@test",
        )
        card = ledger.create_rate_card(data)
        assert card.provider == "openai"
        assert card.status == "draft"
        assert card.rate_card_id is not None

    def test_activate_rate_card(self, now):
        ledger = InMemoryMeteringLedger()
        data = RateCardCreate(
            provider="openai",
            model="gpt-4.1",
            rate_usd=Decimal("0.00003"),
            effective_from=now,
            created_by="admin@test",
        )
        card = ledger.create_rate_card(data)
        activated = ledger.activate_rate_card(card.rate_card_id, activated_by="superadmin@test")
        assert activated is not None
        assert activated.status == "active"
        assert activated.activated_by == "superadmin@test"

    def test_update_rate_card(self, now):
        ledger = InMemoryMeteringLedger()
        data = RateCardCreate(
            provider="openai",
            model="gpt-4.1",
            rate_usd=Decimal("0.00003"),
            effective_from=now,
            created_by="admin@test",
        )
        card = ledger.create_rate_card(data)
        updated = ledger.update_rate_card(
            card.rate_card_id,
            RateCardUpdate(rate_usd=Decimal("0.00004")),
        )
        assert updated is not None
        assert updated.rate_usd == Decimal("0.00004")

    def test_delete_rate_card(self, now):
        ledger = InMemoryMeteringLedger()
        data = RateCardCreate(
            provider="openai",
            model="gpt-4.1",
            rate_usd=Decimal("0.00003"),
            effective_from=now,
            created_by="admin@test",
        )
        card = ledger.create_rate_card(data)
        assert ledger.delete_rate_card(card.rate_card_id) is True
        assert ledger.get_rate_card(card.rate_card_id) is None

    def test_list_rate_cards_filters_by_status(self, now):
        ledger = InMemoryMeteringLedger()
        ledger.create_rate_card(RateCardCreate(
            provider="openai", model="gpt-4.1", rate_usd=Decimal("0.00003"),
            effective_from=now, created_by="admin@test",
        ))
        card2 = ledger.create_rate_card(RateCardCreate(
            provider="anthropic", model="claude-3", rate_usd=Decimal("0.00005"),
            effective_from=now, created_by="admin@test",
        ))
        ledger.activate_rate_card(card2.rate_card_id, activated_by="admin@test")
        active = ledger.list_rate_cards(status="active")
        assert len(active) == 1
        assert active[0].provider == "anthropic"


class TestProviderRequestIdOnUsage:
    def test_usage_record_with_provider_request_id(self, usage_record):
        assert usage_record.provider_request_id == "req-abc-123"

    def test_usage_record_without_provider_request_id(self, now):
        record = UsageRecord(
            usage_id=str(uuid4()),
            tenant_id="tenant-test",
            team_id="team-alpha",
            run_id="run-2",
            ticket_key="PROJ-456",
            role="planner",
            provider_id="openai",
            model_id="gpt-4.1",
            deployment_profile="connected",
            input_tokens=500,
            output_tokens=200,
            latency_ms=100,
            estimated_cost_usd=Decimal("0.02"),
            actual_cost_usd=Decimal("0.018"),
            rate_card_id="card-openai-v1",
            trace_id="trace-2",
            span_id="span-2",
            started_at=now - timedelta(minutes=10),
            completed_at=now,
        )
        assert record.provider_request_id is None


class TestReconciliation:
    def test_reconciliation_no_drift(self, now):
        ledger = InMemoryMeteringLedger()
        report = ledger.run_reconciliation(
            tenant_id="tenant-test",
            period_start=now - timedelta(hours=1),
            period_end=now,
            provider="openai",
            provider_reported_total_usd=Decimal("0.045"),
            mode="dry_run",
        )
        assert report.metered_total_usd == Decimal("0")
        assert report.drift_amount_usd == Decimal("0.045")

    def test_reconciliation_with_usage(self, now, usage_record):
        ledger = InMemoryMeteringLedger()
        ledger.record_usage(usage_record)
        report = ledger.run_reconciliation(
            tenant_id="tenant-test",
            period_start=now - timedelta(hours=1),
            period_end=now + timedelta(hours=1),
            provider="openai",
            provider_reported_total_usd=Decimal("0.045"),
            mode="dry_run",
        )
        assert report.metered_total_usd == Decimal("0.045")
        assert report.drift_amount_usd == Decimal("0")
        assert report.drift_percentage == Decimal("0")
        assert report.matched_usage_count == 1
        assert report.missing_provider_request_ids == 0

    def test_reconciliation_drift_exceeds_threshold(self, now, usage_record):
        ledger = InMemoryMeteringLedger()
        ledger.record_usage(usage_record)
        report = ledger.run_reconciliation(
            tenant_id="tenant-test",
            period_start=now - timedelta(hours=1),
            period_end=now + timedelta(hours=1),
            provider="openai",
            provider_reported_total_usd=Decimal("0.10"),
            mode="dry_run",
        )
        assert abs(report.drift_percentage) > 2
        assert report.mode == "dry_run"

    def test_reconciliation_missing_provider_request_ids(self, now):
        ledger = InMemoryMeteringLedger()
        record = UsageRecord(
            usage_id=str(uuid4()),
            tenant_id="tenant-test",
            team_id="team-alpha",
            run_id="run-3",
            ticket_key="PROJ-789",
            role="tester",
            provider_id="openai",
            model_id="gpt-4.1",
            deployment_profile="connected",
            input_tokens=800,
            output_tokens=300,
            latency_ms=150,
            estimated_cost_usd=Decimal("0.03"),
            actual_cost_usd=Decimal("0.028"),
            rate_card_id="card-openai-v1",
            trace_id="trace-3",
            span_id="span-3",
            started_at=now - timedelta(minutes=15),
            completed_at=now,
        )
        ledger.record_usage(record)
        report = ledger.run_reconciliation(
            tenant_id="tenant-test",
            period_start=now - timedelta(hours=1),
            period_end=now + timedelta(hours=1),
            provider="openai",
            provider_reported_total_usd=Decimal("0.028"),
            mode="dry_run",
        )
        assert report.missing_provider_request_ids == 1

    def test_reconciliation_report_persisted(self, now, usage_record):
        ledger = InMemoryMeteringLedger()
        ledger.record_usage(usage_record)
        report = ledger.run_reconciliation(
            tenant_id="tenant-test",
            period_start=now - timedelta(hours=1),
            period_end=now + timedelta(hours=1),
            provider="openai",
            provider_reported_total_usd=Decimal("0.045"),
            mode="dry_run",
        )
        reports = ledger.list_reconciliation_reports(tenant_id="tenant-test")
        assert len(reports) == 1
        assert reports[0].report_id == report.report_id


class TestBillingExport:
    def test_export_csv_includes_rate_card_id(self, now, usage_record):
        ledger = InMemoryMeteringLedger()
        ledger.record_usage(usage_record)
        content = ledger.export(
            type("MeteringExportRequest", (), {
                "tenant_id": "tenant-test",
                "period_start": now - timedelta(hours=1),
                "period_end": now + timedelta(hours=1),
                "format": "csv",
                "schema_version": "v1",
            })()
        )
        assert "rate_card_id" in content
        assert "card-openai-v1" in content

    def test_export_json_v2(self, now, usage_record):
        ledger = InMemoryMeteringLedger()
        ledger.record_usage(usage_record)
        content = ledger.export(
            type("MeteringExportRequest", (), {
                "tenant_id": "tenant-test",
                "period_start": now - timedelta(hours=1),
                "period_end": now + timedelta(hours=1),
                "format": "jsonl",
                "schema_version": "v2",
            })()
        )
        assert "schema_version" in content
        assert "v2" in content
        assert "provider_request_id" in content
