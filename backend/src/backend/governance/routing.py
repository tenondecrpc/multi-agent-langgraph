from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .budget import BudgetContext
from .catalog import DeploymentProfile, InMemoryModelCatalog, RuntimeRole


class RoleModelAssignment(BaseModel):
    role: RuntimeRole
    primary_model_id: str
    fallback_model_id: str | None = None


class ProviderHealthState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ProviderHealthSnapshot(BaseModel):
    provider_id: str
    state: ProviderHealthState = ProviderHealthState.CLOSED
    consecutive_failures: int = 0
    remaining_probe_attempts: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class ProviderSelection(BaseModel):
    provider_id: str
    model_id: str
    fallback_used: bool = False


class ProviderRoutingError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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


class RuleBasedProviderRouter:
    def __init__(
        self,
        *,
        model_catalog: InMemoryModelCatalog,
        health_store: InMemoryProviderHealthStore,
        role_assignments: list[RoleModelAssignment],
    ) -> None:
        self.model_catalog = model_catalog
        self.health_store = health_store
        self._role_assignments = {
            assignment.role: assignment for assignment in role_assignments
        }

    def select_model(
        self,
        *,
        role: RuntimeRole,
        run_id: str,
        tenant_id: str,
        budget_context: BudgetContext,
        deployment_profile: DeploymentProfile,
    ) -> ProviderSelection:
        del run_id, tenant_id, budget_context

        assignment = self._role_assignments[role]
        primary = self.model_catalog.resolve_model(
            assignment.primary_model_id,
            deployment_profile,
        )

        fallback = None
        if assignment.fallback_model_id is not None:
            self.model_catalog.validate_fallback(
                primary_model_id=assignment.primary_model_id,
                fallback_model_id=assignment.fallback_model_id,
                deployment_profile=deployment_profile,
            )
            fallback = self.model_catalog.resolve_model(
                assignment.fallback_model_id,
                deployment_profile,
            )

        if self.health_store.allow_request(primary.provider_id):
            return ProviderSelection(
                provider_id=primary.provider_id,
                model_id=primary.model_id,
            )

        if fallback is None:
            raise ProviderRoutingError("provider_failover_exhausted")

        if self.health_store.allow_request(fallback.provider_id):
            return ProviderSelection(
                provider_id=fallback.provider_id,
                model_id=fallback.model_id,
                fallback_used=True,
            )

        raise ProviderRoutingError("all_providers_unavailable")
