from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from backend.persistence.contracts import ModelCatalog, ProviderHealthStore

from .budget import BudgetContext
from .catalog import DeploymentProfile, RuntimeRole

if TYPE_CHECKING:
    from backend.persistence.testing.governance import InMemoryProviderHealthStore


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


class RuleBasedProviderRouter:
    def __init__(
        self,
        *,
        model_catalog: ModelCatalog,
        health_store: ProviderHealthStore,
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


__all__ = [
    "InMemoryProviderHealthStore",
    "ProviderHealthSnapshot",
    "ProviderHealthState",
    "ProviderRoutingError",
    "ProviderSelection",
    "RoleModelAssignment",
    "RuleBasedProviderRouter",
]


def __getattr__(name: str):
    if name == "InMemoryProviderHealthStore":
        from backend.persistence.testing.governance import InMemoryProviderHealthStore

        return InMemoryProviderHealthStore
    raise AttributeError(name)
