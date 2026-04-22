from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

from .catalog import RuntimeRole

if TYPE_CHECKING:
    from backend.persistence.testing.governance import InMemoryBudgetLedger


class BudgetContext(BaseModel):
    tenant_id: str
    team_id: str
    run_id: str
    ticket_key: str
    role: RuntimeRole


class BudgetCaps(BaseModel):
    ticket_cap_usd: Decimal
    daily_team_cap_usd: Decimal
    monthly_team_cap_usd: Decimal


class BudgetReservation(BaseModel):
    reservation_id: str
    reserved_amount_usd: Decimal
    ticket_cap_remaining_usd: Decimal
    daily_team_cap_remaining_usd: Decimal
    monthly_team_cap_remaining_usd: Decimal


class BudgetBalance(BaseModel):
    ticket_remaining_usd: Decimal
    daily_team_remaining_usd: Decimal
    monthly_team_remaining_usd: Decimal


class BudgetSettlement(BaseModel):
    reservation_id: str
    estimated_cost_usd: Decimal
    actual_cost_usd: Decimal
    refunded_amount_usd: Decimal


class OrphanedReservationRelease(BaseModel):
    reservation_id: str
    released_amount_usd: Decimal
    reason: str


class _ActiveReservation(BaseModel):
    reservation_id: str
    context: BudgetContext
    reserved_amount_usd: Decimal


class BudgetExceededError(Exception):
    def __init__(self, reason: str = "budget_exhausted") -> None:
        super().__init__(reason)
        self.reason = reason


__all__ = [
    "BudgetBalance",
    "BudgetCaps",
    "BudgetContext",
    "BudgetExceededError",
    "BudgetReservation",
    "BudgetSettlement",
    "InMemoryBudgetLedger",
    "OrphanedReservationRelease",
]


def __getattr__(name: str):
    if name == "InMemoryBudgetLedger":
        from backend.persistence.testing.governance import InMemoryBudgetLedger

        return InMemoryBudgetLedger
    raise AttributeError(name)
