from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .catalog import DeploymentProfile, RuntimeRole

if TYPE_CHECKING:
    from backend.persistence.testing.governance import InMemoryMeteringLedger


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
    provider_request_id: str | None = None
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
    schema_version: str = "v1"
    sealed_period_only: bool = True


class ReconciliationResult(BaseModel):
    period_start: datetime
    period_end: datetime
    metered_total_usd: Decimal
    provider_reported_total_usd: Decimal
    drift_amount_usd: Decimal
    usage_ids: list[str]
    rollup_ids: list[str]


class RateCard(BaseModel):
    rate_card_id: str
    provider: str
    model: str
    unit: str = "per_1k_tokens"
    rate_usd: Decimal
    effective_from: datetime
    effective_to: datetime | None = None
    version: int = 1
    status: str = "draft"
    created_by: str
    activated_by: str | None = None
    activated_at: datetime | None = None
    metadata: dict = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RateCardCreate(BaseModel):
    provider: str
    model: str
    unit: str = "per_1k_tokens"
    rate_usd: Decimal
    effective_from: datetime
    effective_to: datetime | None = None
    created_by: str
    metadata: dict = {}


class RateCardUpdate(BaseModel):
    rate_usd: Decimal | None = None
    effective_to: datetime | None = None
    metadata: dict | None = None


class ReconciliationReport(BaseModel):
    report_id: str
    tenant_id: str
    period_start: datetime
    period_end: datetime
    provider: str
    metered_total_usd: Decimal
    provider_reported_total_usd: Decimal
    drift_amount_usd: Decimal
    drift_percentage: Decimal
    missing_provider_request_ids: int = 0
    matched_usage_count: int = 0
    unmatched_usage_count: int = 0
    mode: str = "dry_run"
    usage_ids: list[str] = []
    rollup_ids: list[str] = []
    created_at: datetime | None = None


__all__ = [
    "HourlyUsageRollup",
    "InMemoryMeteringLedger",
    "MeteringExportRequest",
    "RateCard",
    "RateCardCreate",
    "RateCardUpdate",
    "ReconciliationReport",
    "ReconciliationResult",
    "UsageRecord",
    "UsageStatus",
]


def __getattr__(name: str):
    if name == "InMemoryMeteringLedger":
        from backend.persistence.testing.governance import InMemoryMeteringLedger

        return InMemoryMeteringLedger
    raise AttributeError(name)
