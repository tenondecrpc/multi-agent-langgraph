from __future__ import annotations

from decimal import Decimal
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel

from .catalog import RuntimeRole


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
