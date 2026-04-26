from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
from threading import Lock
from uuid import uuid4

from backend.governance.budget import (
    BudgetBalance,
    BudgetCaps,
    BudgetContext,
    BudgetExceededError,
    BudgetReservation,
    BudgetSettlement,
    OrphanedReservationRelease,
)
from backend.governance.catalog import (
    DeploymentProfile,
    ModelCatalogEntry,
    RoleTokenPolicy,
    RuntimeRole,
    TokenCap,
)
from backend.governance.metering import (
    HourlyUsageRollup,
    MeteringExportRequest,
    ReconciliationResult,
    UsageRecord,
)
from backend.governance.routing import ProviderHealthSnapshot, ProviderHealthState


class _ActiveReservation:
    def __init__(
        self,
        *,
        reservation_id: str,
        context: BudgetContext,
        reserved_amount_usd: Decimal,
    ) -> None:
        self.reservation_id = reservation_id
        self.context = context
        self.reserved_amount_usd = reserved_amount_usd


class InMemoryBudgetLedger:
    def __init__(self) -> None:
        self._lock = Lock()
        self._caps_by_run: dict[str, BudgetCaps] = {}
        self._team_caps: dict[tuple[str, str], BudgetCaps] = {}
        self._ticket_spend: dict[str, Decimal] = {}
        self._team_daily_spend: dict[tuple[str, str], Decimal] = {}
        self._team_monthly_spend: dict[tuple[str, str], Decimal] = {}
        self._active_reservations: dict[str, _ActiveReservation] = {}
        self.settlements: list[BudgetSettlement] = []
        self.orphaned_releases: list[OrphanedReservationRelease] = []

    def configure_caps(self, context: BudgetContext, caps: BudgetCaps) -> None:
        self._caps_by_run[context.run_id] = caps
        self._team_caps[(context.tenant_id, context.team_id)] = caps

    def reserve(
        self,
        context: BudgetContext,
        worst_case_cost_usd: Decimal,
    ) -> BudgetReservation:
        with self._lock:
            caps = self._caps_for_context(context)
            ticket_used = self._ticket_spend.get(context.run_id, Decimal("0"))
            team_key = (context.tenant_id, context.team_id)
            daily_used = self._team_daily_spend.get(team_key, Decimal("0"))
            monthly_used = self._team_monthly_spend.get(team_key, Decimal("0"))

            ticket_reserved = self._reserved_amount_for_run(context.run_id)
            team_reserved = self._reserved_amount_for_team(team_key)

            if ticket_used + ticket_reserved + worst_case_cost_usd > caps.ticket_cap_usd:
                raise BudgetExceededError()
            if daily_used + team_reserved + worst_case_cost_usd > caps.daily_team_cap_usd:
                raise BudgetExceededError()
            if monthly_used + team_reserved + worst_case_cost_usd > caps.monthly_team_cap_usd:
                raise BudgetExceededError()

            reservation_id = str(uuid4())
            reservation = _ActiveReservation(
                reservation_id=reservation_id,
                context=context,
                reserved_amount_usd=worst_case_cost_usd,
            )
            self._active_reservations[reservation_id] = reservation

            return BudgetReservation(
                reservation_id=reservation_id,
                reserved_amount_usd=worst_case_cost_usd,
                ticket_cap_remaining_usd=(
                    caps.ticket_cap_usd - (ticket_used + ticket_reserved + worst_case_cost_usd)
                ),
                daily_team_cap_remaining_usd=(
                    caps.daily_team_cap_usd - (daily_used + team_reserved + worst_case_cost_usd)
                ),
                monthly_team_cap_remaining_usd=(
                    caps.monthly_team_cap_usd - (monthly_used + team_reserved + worst_case_cost_usd)
                ),
            )

    def settle(self, reservation_id: str, actual_cost_usd: Decimal) -> None:
        with self._lock:
            reservation = self._active_reservations.pop(reservation_id)
            if actual_cost_usd > reservation.reserved_amount_usd:
                raise ValueError(
                    "Actual cost exceeded the reserved worst-case estimate."
                )

            team_key = (reservation.context.tenant_id, reservation.context.team_id)
            self._ticket_spend[reservation.context.run_id] = (
                self._ticket_spend.get(reservation.context.run_id, Decimal("0"))
                + actual_cost_usd
            )
            self._team_daily_spend[team_key] = (
                self._team_daily_spend.get(team_key, Decimal("0")) + actual_cost_usd
            )
            self._team_monthly_spend[team_key] = (
                self._team_monthly_spend.get(team_key, Decimal("0")) + actual_cost_usd
            )
            self.settlements.append(
                BudgetSettlement(
                    reservation_id=reservation_id,
                    estimated_cost_usd=reservation.reserved_amount_usd,
                    actual_cost_usd=actual_cost_usd,
                    refunded_amount_usd=reservation.reserved_amount_usd - actual_cost_usd,
                )
            )

    def release_orphaned(self, reservation_id: str, reason: str) -> None:
        with self._lock:
            reservation = self._active_reservations.pop(reservation_id)
            self.orphaned_releases.append(
                OrphanedReservationRelease(
                    reservation_id=reservation_id,
                    released_amount_usd=reservation.reserved_amount_usd,
                    reason=reason,
                )
            )

    def balance(self, context: BudgetContext) -> BudgetBalance:
        caps = self._caps_for_context(context)
        team_key = (context.tenant_id, context.team_id)
        ticket_used = self._ticket_spend.get(context.run_id, Decimal("0"))
        daily_used = self._team_daily_spend.get(team_key, Decimal("0"))
        monthly_used = self._team_monthly_spend.get(team_key, Decimal("0"))

        ticket_reserved = self._reserved_amount_for_run(context.run_id)
        team_reserved = self._reserved_amount_for_team(team_key)
        return BudgetBalance(
            ticket_remaining_usd=caps.ticket_cap_usd - (ticket_used + ticket_reserved),
            daily_team_remaining_usd=caps.daily_team_cap_usd - (daily_used + team_reserved),
            monthly_team_remaining_usd=caps.monthly_team_cap_usd - (monthly_used + team_reserved),
        )

    def _caps_for_context(self, context: BudgetContext) -> BudgetCaps:
        team_key = (context.tenant_id, context.team_id)
        if context.run_id not in self._caps_by_run or team_key not in self._team_caps:
            raise ValueError(
                f"Budget caps were not configured for run `{context.run_id}`."
            )
        return self._caps_by_run[context.run_id]

    def _reserved_amount_for_run(self, run_id: str) -> Decimal:
        return sum(
            (
                reservation.reserved_amount_usd
                for reservation in self._active_reservations.values()
                if reservation.context.run_id == run_id
            ),
            start=Decimal("0"),
        )

    def _reserved_amount_for_team(self, team_key: tuple[str, str]) -> Decimal:
        return sum(
            (
                reservation.reserved_amount_usd
                for reservation in self._active_reservations.values()
                if (reservation.context.tenant_id, reservation.context.team_id) == team_key
            ),
            start=Decimal("0"),
        )


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
            return self._export_csv(records, schema_version=request.schema_version)
        if request.format == "jsonl":
            if request.schema_version == "v2":
                return "\n".join(
                    json.dumps(
                        {
                            "schema_version": "v2",
                            "usage": record.model_dump(mode="json"),
                        }
                    )
                    for record in records
                )
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

    def _export_csv(self, records: list[UsageRecord], *, schema_version: str) -> str:
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
        if schema_version == "v2":
            fieldnames = ["schema_version", *fieldnames]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = record.model_dump(mode="json")
            if schema_version == "v2":
                row = {"schema_version": "v2", **row}
            writer.writerow(row)
        return buffer.getvalue()


class InMemoryModelCatalog:
    def __init__(
        self,
        *,
        entries: list[ModelCatalogEntry],
        role_token_policies: list[RoleTokenPolicy],
    ) -> None:
        self._entries = {
            (entry.model_id, entry.deployment_profile): entry for entry in entries
        }
        self._role_token_policies = {
            policy.role: policy for policy in role_token_policies
        }

    def resolve_model(
        self,
        model_id: str,
        deployment_profile: DeploymentProfile,
    ) -> ModelCatalogEntry:
        try:
            return self._entries[(model_id, deployment_profile)]
        except KeyError as exc:
            raise ValueError(
                f"Unknown model `{model_id}` for deployment profile `{deployment_profile}`."
            ) from exc

    def validate_fallback(
        self,
        *,
        primary_model_id: str,
        fallback_model_id: str,
        deployment_profile: DeploymentProfile,
    ) -> None:
        primary = self.resolve_model(primary_model_id, deployment_profile)
        self.resolve_model(fallback_model_id, deployment_profile)
        if fallback_model_id not in primary.allowed_fallback_targets:
            raise ValueError(
                f"Model `{fallback_model_id}` is not an allowed fallback for `{primary_model_id}`."
            )

    def effective_token_cap(
        self,
        *,
        role: RuntimeRole,
        model_id: str,
        deployment_profile: DeploymentProfile,
        tenant_override: TokenCap | None = None,
    ) -> TokenCap:
        entry = self.resolve_model(model_id, deployment_profile)
        role_policy = self._role_token_policies[role]
        input_limit = min(entry.max_input_tokens, role_policy.max_input_tokens)
        output_limit = min(entry.max_output_tokens, role_policy.max_output_tokens)

        if tenant_override is not None:
            input_limit = min(input_limit, tenant_override.input_tokens)
            output_limit = min(output_limit, tenant_override.output_tokens)

        return TokenCap(
            input_tokens=input_limit,
            output_tokens=output_limit,
        )


class InMemoryProviderHealthStore:
    def __init__(
        self,
        *,
        failure_threshold: int = 2,
        recovery_probe_limit: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_probe_limit = recovery_probe_limit
        self._snapshots: dict[str, ProviderHealthSnapshot] = {}

    def snapshot(self, provider_id: str) -> ProviderHealthSnapshot:
        return self._ensure(provider_id).model_copy(deep=True)

    def record_failure(self, provider_id: str) -> None:
        snapshot = self._ensure(provider_id)
        snapshot.consecutive_failures += 1
        if snapshot.consecutive_failures >= self.failure_threshold:
            snapshot.state = ProviderHealthState.OPEN
            snapshot.remaining_probe_attempts = 0
        snapshot.updated_at = datetime.now(tz=UTC)

    def record_success(self, provider_id: str) -> None:
        snapshot = self._ensure(provider_id)
        snapshot.state = ProviderHealthState.CLOSED
        snapshot.consecutive_failures = 0
        snapshot.remaining_probe_attempts = 0
        snapshot.updated_at = datetime.now(tz=UTC)

    def move_to_half_open(self, provider_id: str) -> None:
        snapshot = self._ensure(provider_id)
        snapshot.state = ProviderHealthState.HALF_OPEN
        snapshot.remaining_probe_attempts = self.recovery_probe_limit
        snapshot.updated_at = datetime.now(tz=UTC)

    def allow_request(self, provider_id: str) -> bool:
        snapshot = self._ensure(provider_id)
        if snapshot.state == ProviderHealthState.OPEN:
            return False
        if snapshot.state == ProviderHealthState.HALF_OPEN:
            if snapshot.remaining_probe_attempts <= 0:
                return False
            snapshot.remaining_probe_attempts -= 1
            snapshot.updated_at = datetime.now(tz=UTC)
        return True

    def _ensure(self, provider_id: str) -> ProviderHealthSnapshot:
        if provider_id not in self._snapshots:
            self._snapshots[provider_id] = ProviderHealthSnapshot(provider_id=provider_id)
        return self._snapshots[provider_id]
