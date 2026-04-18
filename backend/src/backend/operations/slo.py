from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class SliDefinition(BaseModel):
    sli_id: str
    objective_percent: Decimal
    measurement_window: str
    numerator_query: str
    denominator_query: str
    exclusion_query: str | None = None


class SliObservation(BaseModel):
    total_events: int
    successful_events: int
    excluded_events: int = 0


class SliEvaluation(BaseModel):
    effective_total: int
    effective_success: int
    availability_percent: Decimal
    objective_percent: Decimal
    error_budget_remaining_percent: Decimal


class BurnRateAlertPolicy(BaseModel):
    sli_id: str
    short_window: str
    long_window: str
    warning_burn_rate: Decimal
    critical_burn_rate: Decimal


class BurnRateDecision(BaseModel):
    triggered: bool
    severity: str


class ErrorBudgetState(StrEnum):
    HEALTHY = "healthy"
    LOW = "low"
    EXHAUSTED = "exhausted"


class ErrorBudgetReport(BaseModel):
    sli_id: str
    state: ErrorBudgetState
    remaining_percent: Decimal
    release_blocked: bool


class SliEvaluator:
    def evaluate(self, definition: SliDefinition, observation: SliObservation) -> SliEvaluation:
        effective_total = max(observation.total_events - observation.excluded_events, 0)
        effective_success = min(observation.successful_events, effective_total)
        availability = (
            Decimal(effective_success) / Decimal(effective_total) * Decimal("100")
            if effective_total
            else Decimal("100")
        )
        allowed_failure_rate = Decimal("100") - definition.objective_percent
        actual_failure_rate = Decimal("100") - availability
        if allowed_failure_rate <= 0:
            remaining = Decimal("0")
        else:
            remaining = max(
                Decimal("0"),
                Decimal("100")
                - (actual_failure_rate / allowed_failure_rate * Decimal("100")),
            )
        return SliEvaluation(
            effective_total=effective_total,
            effective_success=effective_success,
            availability_percent=availability.quantize(Decimal("0.01")),
            objective_percent=definition.objective_percent,
            error_budget_remaining_percent=remaining.quantize(Decimal("0.01")),
        )

    def evaluate_burn_rate(
        self,
        policy: BurnRateAlertPolicy,
        *,
        current_burn_rate: Decimal,
    ) -> BurnRateDecision:
        if current_burn_rate >= policy.critical_burn_rate:
            return BurnRateDecision(triggered=True, severity="critical")
        if current_burn_rate >= policy.warning_burn_rate:
            return BurnRateDecision(triggered=True, severity="warning")
        return BurnRateDecision(triggered=False, severity="none")

    def error_budget_report(self, definition: SliDefinition, evaluation: SliEvaluation) -> ErrorBudgetReport:
        if evaluation.error_budget_remaining_percent <= Decimal("0"):
            state = ErrorBudgetState.EXHAUSTED
        elif evaluation.error_budget_remaining_percent <= Decimal("50"):
            state = ErrorBudgetState.LOW
        else:
            state = ErrorBudgetState.HEALTHY
        return ErrorBudgetReport(
            sli_id=definition.sli_id,
            state=state,
            remaining_percent=evaluation.error_budget_remaining_percent,
            release_blocked=state == ErrorBudgetState.EXHAUSTED,
        )
