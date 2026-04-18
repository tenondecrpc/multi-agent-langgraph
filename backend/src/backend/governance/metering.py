from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from io import StringIO

from pydantic import BaseModel, Field

from .catalog import DeploymentProfile, RuntimeRole


class UsageStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PROVIDER_FAILURE = "provider_failure"
    BUDGET_REJECTED = "budget_rejected"
    SETTLEMENT_RECOVERED = "settlement_recovered"


class UsageRecord(BaseModel):
    usage_id: str
    tenant_id: str
    team_id: str
    run_id: str
    ticket_key: str
    role: RuntimeRole
    provider_id: str
    model_id: str
    deployment_profile: DeploymentProfile
    fallback_used: bool = False
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    latency_ms: int
    request_count: int = 1
    reservation_id: str | None = None
    estimated_cost_usd: Decimal
    actual_cost_usd: Decimal
    rate_card_id: str
    trace_id: str
    span_id: str
    started_at: datetime
    completed_at: datetime
    status: UsageStatus = UsageStatus.SUCCEEDED


class HourlyUsageRollup(BaseModel):
    rollup_id: str
    bucket_start: datetime
    tenant_id: str
    team_id: str
    role: RuntimeRole
    provider_id: str
    model_id: str
    rate_card_id: str
    request_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_actual_cost_usd: Decimal
    usage_ids: list[str] = Field(default_factory=list)


class MeteringExportRequest(BaseModel):
    tenant_id: str
    period_start: datetime
    period_end: datetime
    format: str
    sealed_period_only: bool = True


class ReconciliationResult(BaseModel):
    period_start: datetime
    period_end: datetime
    metered_total_usd: Decimal
    provider_reported_total_usd: Decimal
    drift_amount_usd: Decimal
    usage_ids: list[str]
    rollup_ids: list[str]


class InMemoryMeteringLedger:
    def __init__(self) -> None:
        self._records: list[UsageRecord] = []

    def record_usage(self, record: UsageRecord) -> None:
        self._records.append(record)

    def build_hourly_rollups(
        self,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> list[HourlyUsageRollup]:
        groups: dict[
            tuple[datetime, str, str, RuntimeRole, str, str, str],
            HourlyUsageRollup,
        ] = {}
        for record in self._filtered_records(tenant_id, period_start, period_end):
            bucket_start = record.completed_at.replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            key = (
                bucket_start,
                record.tenant_id,
                record.team_id,
                record.role,
                record.provider_id,
                record.model_id,
                record.rate_card_id,
            )
            if key not in groups:
                groups[key] = HourlyUsageRollup(
                    rollup_id=(
                        f"{bucket_start.isoformat()}:{record.team_id}:{record.role}:"
                        f"{record.provider_id}:{record.model_id}:{record.rate_card_id}"
                    ),
                    bucket_start=bucket_start,
                    tenant_id=record.tenant_id,
                    team_id=record.team_id,
                    role=record.role,
                    provider_id=record.provider_id,
                    model_id=record.model_id,
                    rate_card_id=record.rate_card_id,
                    request_count=0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_actual_cost_usd=Decimal("0"),
                )

            rollup = groups[key]
            rollup.request_count += record.request_count
            rollup.total_input_tokens += record.input_tokens
            rollup.total_output_tokens += record.output_tokens
            rollup.total_actual_cost_usd += record.actual_cost_usd
            rollup.usage_ids.append(record.usage_id)

        return list(groups.values())

    def export(self, request: MeteringExportRequest) -> str:
        records = self._filtered_records(
            request.tenant_id,
            request.period_start,
            request.period_end,
        )
        if request.format == "csv":
            return self._export_csv(records)
        if request.format == "jsonl":
            return "\n".join(record.model_dump_json() for record in records)
        raise ValueError(f"Unsupported export format `{request.format}`.")

    def reconcile(
        self,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
        provider_reported_total_usd: Decimal,
    ) -> ReconciliationResult:
        records = self._filtered_records(tenant_id, period_start, period_end)
        rollups = self.build_hourly_rollups(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
        )
        metered_total = sum(
            (record.actual_cost_usd for record in records),
            start=Decimal("0"),
        )
        return ReconciliationResult(
            period_start=period_start,
            period_end=period_end,
            metered_total_usd=metered_total,
            provider_reported_total_usd=provider_reported_total_usd,
            drift_amount_usd=provider_reported_total_usd - metered_total,
            usage_ids=[record.usage_id for record in records],
            rollup_ids=[rollup.rollup_id for rollup in rollups],
        )

    def _filtered_records(
        self,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> list[UsageRecord]:
        return [
            record
            for record in self._records
            if record.tenant_id == tenant_id
            and period_start <= record.completed_at <= period_end
        ]

    def _export_csv(self, records: list[UsageRecord]) -> str:
        buffer = StringIO()
        fieldnames = [
            "usage_id",
            "tenant_id",
            "team_id",
            "run_id",
            "ticket_key",
            "role",
            "provider_id",
            "model_id",
            "deployment_profile",
            "fallback_used",
            "input_tokens",
            "output_tokens",
            "cached_tokens",
            "latency_ms",
            "request_count",
            "reservation_id",
            "estimated_cost_usd",
            "actual_cost_usd",
            "rate_card_id",
            "trace_id",
            "span_id",
            "started_at",
            "completed_at",
            "status",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record.model_dump(mode="json"))
        return buffer.getvalue()
