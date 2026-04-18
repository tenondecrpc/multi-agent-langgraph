from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class QualitySuiteDefinition(BaseModel):
    suite_id: str
    layer: Literal["unit", "integration", "e2e", "chaos", "fuzz", "prompt_regression"]
    required_on_pr: bool = False
    required_on_release: bool = False


class CoveragePolicy(BaseModel):
    unit_floor_percent: Decimal
    integration_floor_percent: Decimal


class CoverageWaiver(BaseModel):
    waiver_id: str
    layer: Literal["unit", "integration"]
    approved_by: str
    rationale: str


class CoverageDecision(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    waiver_used: str | None = None


class QualityGateService:
    REQUIRED_LAYERS = {"unit", "integration", "e2e", "chaos", "fuzz", "prompt_regression"}

    def validate_quality_program(self, suites: list[QualitySuiteDefinition]) -> CoverageDecision:
        configured_layers = {suite.layer for suite in suites}
        missing_layers = sorted(self.REQUIRED_LAYERS - configured_layers)
        return CoverageDecision(
            allowed=not missing_layers,
            reasons=[f"missing_layer:{layer}" for layer in missing_layers],
        )

    def evaluate_coverage(
        self,
        policy: CoveragePolicy,
        *,
        unit_coverage_percent: Decimal,
        integration_coverage_percent: Decimal,
        waiver: CoverageWaiver | None = None,
    ) -> CoverageDecision:
        reasons: list[str] = []
        if unit_coverage_percent < policy.unit_floor_percent:
            reasons.append("unit_coverage_below_floor")
        if integration_coverage_percent < policy.integration_floor_percent:
            reasons.append("integration_coverage_below_floor")
        if not reasons:
            return CoverageDecision(allowed=True)
        if waiver is not None:
            return CoverageDecision(
                allowed=True,
                reasons=reasons,
                waiver_used=waiver.waiver_id,
            )
        return CoverageDecision(allowed=False, reasons=reasons)

    def evaluate_static_gates(self, gate_results: dict[str, bool]) -> CoverageDecision:
        failing = [
            gate_name for gate_name, passed in gate_results.items() if not passed
        ]
        return CoverageDecision(
            allowed=not failing,
            reasons=[f"gate_failed:{gate_name}" for gate_name in failing],
        )
