from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class ShadowIsolationProfile(BaseModel):
    candidate_version_id: str
    queue_isolated: bool = True
    read_only_credentials: bool = True
    isolated_worker_identity: bool = True
    restricted_network_policy: bool = True
    runtime_shadow_flag: bool = True

    def enabled_layers(self) -> int:
        return sum(
            [
                self.queue_isolated,
                self.read_only_credentials,
                self.isolated_worker_identity,
                self.restricted_network_policy,
                self.runtime_shadow_flag,
            ]
        )

    def blocks_write_side_effects(self) -> bool:
        return self.enabled_layers() >= 4


class ComparisonMetrics(BaseModel):
    baseline_success_rate: float
    candidate_success_rate: float
    baseline_cost_usd: Decimal
    candidate_cost_usd: Decimal
    safety_regressions: list[str] = Field(default_factory=list)


class ActivationThresholds(BaseModel):
    minimum_candidate_success_rate: float
    max_cost_delta_usd: Decimal


class ShadowComparisonReport(BaseModel):
    candidate_version_id: str
    active_version_id: str
    success_rate_delta: float
    cost_delta_usd: Decimal
    safety_regressions: list[str] = Field(default_factory=list)
    blocked: bool
    blocking_reasons: list[str] = Field(default_factory=list)


class ShadowModeEvaluator:
    def build_isolation_profile(self, candidate_version_id: str) -> ShadowIsolationProfile:
        return ShadowIsolationProfile(candidate_version_id=candidate_version_id)

    def compare(
        self,
        *,
        candidate_version_id: str,
        active_version_id: str,
        metrics: ComparisonMetrics,
        thresholds: ActivationThresholds,
    ) -> ShadowComparisonReport:
        success_rate_delta = metrics.candidate_success_rate - metrics.baseline_success_rate
        cost_delta = metrics.candidate_cost_usd - metrics.baseline_cost_usd
        blocking_reasons: list[str] = []

        if metrics.candidate_success_rate < thresholds.minimum_candidate_success_rate:
            blocking_reasons.append("candidate_success_rate_below_threshold")
        if cost_delta > thresholds.max_cost_delta_usd:
            blocking_reasons.append("candidate_cost_exceeds_threshold")
        if metrics.safety_regressions:
            blocking_reasons.append("candidate_introduced_safety_regressions")

        return ShadowComparisonReport(
            candidate_version_id=candidate_version_id,
            active_version_id=active_version_id,
            success_rate_delta=success_rate_delta,
            cost_delta_usd=cost_delta,
            safety_regressions=metrics.safety_regressions,
            blocked=bool(blocking_reasons),
            blocking_reasons=blocking_reasons,
        )
