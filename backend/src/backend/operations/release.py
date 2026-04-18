from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class PipelineStage(BaseModel):
    stage_name: str
    required_gates: list[str]


class StageEvaluationResult(BaseModel):
    passed: bool
    missing_gates: list[str] = Field(default_factory=list)


class RolloutAnalysis(BaseModel):
    error_budget_burn_rate: Decimal
    health_regressed: bool
    kill_switch_engaged: bool = False


class RolloutDecision(BaseModel):
    proceed: bool
    rollback: bool
    reasons: list[str] = Field(default_factory=list)


class MigrationPlan(BaseModel):
    change_id: str
    expand_first: bool
    rollback_tested: bool


class FeatureFlagDefinition(BaseModel):
    flag_id: str
    flag_type: Literal["release", "experiment", "kill_switch"]
    default_enabled: bool = False
    auditable: bool = True


class EnvironmentProfile(BaseModel):
    environment_name: str
    purpose: str
    production_mirror: bool = False


class ReleasePolicy:
    def __init__(
        self,
        *,
        stages: list[PipelineStage],
        environments: list[EnvironmentProfile],
        feature_flags: list[FeatureFlagDefinition],
    ) -> None:
        self._stages = {stage.stage_name: stage for stage in stages}
        self._environments = {env.environment_name: env for env in environments}
        self._feature_flags = {flag.flag_id: flag for flag in feature_flags}

    def evaluate_stage(self, stage_name: str, gate_results: dict[str, bool]) -> StageEvaluationResult:
        stage = self._stages[stage_name]
        missing_gates = [
            gate for gate in stage.required_gates if not gate_results.get(gate, False)
        ]
        return StageEvaluationResult(passed=not missing_gates, missing_gates=missing_gates)

    def evaluate_rollout(self, analysis: RolloutAnalysis) -> RolloutDecision:
        reasons: list[str] = []
        rollback = False
        if analysis.health_regressed:
            reasons.append("health_regressed")
            rollback = True
        if analysis.error_budget_burn_rate > Decimal("2.0"):
            reasons.append("burn_rate_threshold_exceeded")
            rollback = True
        if analysis.kill_switch_engaged:
            reasons.append("kill_switch_engaged")
            rollback = True
        return RolloutDecision(proceed=not rollback, rollback=rollback, reasons=reasons)

    def validate_migration(self, plan: MigrationPlan) -> StageEvaluationResult:
        missing: list[str] = []
        if not plan.expand_first:
            missing.append("expand_first")
        if not plan.rollback_tested:
            missing.append("rollback_tested")
        return StageEvaluationResult(passed=not missing, missing_gates=missing)

    def environment(self, environment_name: str) -> EnvironmentProfile:
        return self._environments[environment_name]

    def feature_flag(self, flag_id: str) -> FeatureFlagDefinition:
        return self._feature_flags[flag_id]
