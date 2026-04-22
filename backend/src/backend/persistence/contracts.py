from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from backend.control_plane.shadow import ShadowComparisonReport
    from backend.control_plane.store import ConfigSnapshot, ConfigVersionRecord, RunState
    from backend.governance.budget import BudgetBalance, BudgetCaps, BudgetContext, BudgetReservation
    from backend.governance.catalog import DeploymentProfile, ModelCatalogEntry, RuntimeRole, TokenCap
    from backend.governance.metering import (
        HourlyUsageRollup,
        MeteringExportRequest,
        ReconciliationResult,
        UsageRecord,
    )
    from backend.platform.queue import DeadLetterRecord, QueuedJob, WorkerDrainLease
    from backend.runtime.models import EscalationReason, RunNode, TenantContext, TicketRunState
    from backend.security.webhook import WebhookGuardResult, WebhookRequest


@runtime_checkable
class RunRepository(Protocol):
    def save(self, run: TicketRunState) -> TicketRunState: ...

    def load(
        self,
        thread_id: str,
        *,
        tenant_context: TenantContext | None = None,
    ) -> TicketRunState | None: ...

    def validate_escalation_sinks(
        self,
        escalation_sinks: Mapping[str, str],
        required_reasons: tuple[EscalationReason, ...] | None = None,
    ) -> None: ...

    def pause(
        self,
        run: TicketRunState,
        node: RunNode,
        reason: EscalationReason,
        escalation_sinks: Mapping[str, str],
    ) -> TicketRunState: ...

    def resume(
        self,
        thread_id: str,
        *,
        tenant_context: TenantContext | None = None,
    ) -> TicketRunState: ...


@runtime_checkable
class ControlPlaneStore(Protocol):
    def create_graph_version(
        self,
        *,
        payload: dict[str, object],
        actor: str,
        rationale: str,
    ) -> ConfigVersionRecord: ...

    def create_agent_version(
        self,
        *,
        payload: dict[str, object],
        actor: str,
        rationale: str,
    ) -> ConfigVersionRecord: ...

    def activate(
        self,
        *,
        graph_version_id: str,
        agent_version_ids: dict[str, str],
        actor: str,
        rationale: str,
        comparison_report: ShadowComparisonReport,
        override_rationale: str | None = None,
        expected_active_snapshot_id: str | None = None,
    ) -> ConfigSnapshot: ...

    def rollback(
        self,
        *,
        snapshot_id: str,
        actor: str,
        rationale: str,
        expected_active_snapshot_id: str | None = None,
    ) -> ConfigSnapshot: ...

    def active_snapshot(self) -> ConfigSnapshot: ...

    def pin_run_snapshot(self, run_id: str, snapshot_id: str, status: RunState) -> None: ...

    def snapshot_for_run(self, run_id: str) -> ConfigSnapshot: ...

    def update_run_status(self, run_id: str, status: RunState) -> None: ...

    def cleanup_retired_snapshots(self) -> list[str]: ...


@runtime_checkable
class HandlerRegistry(Protocol):
    def resolve(self, handler_name: str) -> str | None: ...


@runtime_checkable
class WorkerController(Protocol):
    draining_workers: set[str]

    def assign(self, worker_id: str, job: QueuedJob) -> None: ...

    def begin_drain(self, worker_id: str) -> WorkerDrainLease: ...

    def checkpoint_and_release(self, worker_id: str, checkpoint_ref: str) -> QueuedJob: ...

    def capture_terminal_failure(self, worker_id: str, failure_reason: str) -> DeadLetterRecord: ...


@runtime_checkable
class BudgetLedger(Protocol):
    def configure_caps(self, context: BudgetContext, caps: BudgetCaps) -> None: ...

    def reserve(self, context: BudgetContext, worst_case_cost_usd: Decimal) -> BudgetReservation: ...

    def settle(self, reservation_id: str, actual_cost_usd: Decimal) -> None: ...

    def release_orphaned(self, reservation_id: str, reason: str) -> None: ...

    def balance(self, context: BudgetContext) -> BudgetBalance: ...


@runtime_checkable
class MeteringLedger(Protocol):
    def record_usage(self, record: UsageRecord) -> None: ...

    def build_hourly_rollups(
        self,
        *,
        tenant_id: str,
        period_start,
        period_end,
    ) -> list[HourlyUsageRollup]: ...

    def export(self, request: MeteringExportRequest) -> str: ...

    def reconcile(
        self,
        *,
        tenant_id: str,
        period_start,
        period_end,
        provider_reported_total_usd: Decimal,
    ) -> ReconciliationResult: ...


@runtime_checkable
class ModelCatalog(Protocol):
    def resolve_model(
        self,
        model_id: str,
        deployment_profile: DeploymentProfile,
    ) -> ModelCatalogEntry: ...

    def validate_fallback(
        self,
        *,
        primary_model_id: str,
        fallback_model_id: str,
        deployment_profile: DeploymentProfile,
    ) -> None: ...

    def effective_token_cap(
        self,
        *,
        role: RuntimeRole,
        model_id: str,
        deployment_profile: DeploymentProfile,
        tenant_override: TokenCap | None = None,
    ) -> TokenCap: ...


@runtime_checkable
class ProviderHealthStore(Protocol):
    def snapshot(self, provider_id: str): ...

    def record_failure(self, provider_id: str) -> None: ...

    def record_success(self, provider_id: str) -> None: ...

    def move_to_half_open(self, provider_id: str) -> None: ...

    def allow_request(self, provider_id: str) -> bool: ...


@runtime_checkable
class WebhookGuard(Protocol):
    def verify(self, request: WebhookRequest, *, now: int) -> WebhookGuardResult: ...

    def sign(self, body: str, timestamp: int) -> str: ...
