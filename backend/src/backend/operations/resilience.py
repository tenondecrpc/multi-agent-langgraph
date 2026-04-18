from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RecoveryObjective(BaseModel):
    rpo_minutes: int
    rto_minutes: int


class BackupRecord(BaseModel):
    backup_id: str
    created_at: datetime
    verified: bool = False


class RestoreDrillResult(BaseModel):
    drill_id: str
    restored: bool
    recovery_point_minutes: int
    recovery_time_minutes: int


class RollbackDrillResult(BaseModel):
    drill_id: str
    success: bool
    rollback_time_minutes: int


class ReplicaStrategy(BaseModel):
    primary_count: int
    replica_count: int
    anti_affinity: bool
    pod_disruption_budget: bool
    pooled_connections: bool
    safe_read_paths_defined: bool


class ResilienceAssessment(BaseModel):
    meets_rpo: bool
    meets_rto: bool
    continuity_controls_ready: bool
    reasons: list[str] = Field(default_factory=list)


class ResiliencePlanner:
    def assess_dr(
        self,
        objective: RecoveryObjective,
        *,
        restore_drill: RestoreDrillResult,
        rollback_drill: RollbackDrillResult,
    ) -> ResilienceAssessment:
        reasons: list[str] = []
        meets_rpo = restore_drill.restored and restore_drill.recovery_point_minutes <= objective.rpo_minutes
        meets_rto = restore_drill.restored and restore_drill.recovery_time_minutes <= objective.rto_minutes
        if not meets_rpo:
            reasons.append("rpo_missed")
        if not meets_rto:
            reasons.append("rto_missed")
        if not rollback_drill.success:
            reasons.append("rollback_drill_failed")
        return ResilienceAssessment(
            meets_rpo=meets_rpo,
            meets_rto=meets_rto,
            continuity_controls_ready=not reasons,
            reasons=reasons,
        )

    def validate_replica_strategy(self, strategy: ReplicaStrategy) -> ResilienceAssessment:
        reasons: list[str] = []
        if strategy.primary_count < 1:
            reasons.append("missing_primary")
        if strategy.replica_count < 1:
            reasons.append("missing_replica")
        if not strategy.anti_affinity:
            reasons.append("anti_affinity_missing")
        if not strategy.pod_disruption_budget:
            reasons.append("pod_disruption_budget_missing")
        if not strategy.pooled_connections:
            reasons.append("connection_pooling_missing")
        if not strategy.safe_read_paths_defined:
            reasons.append("read_strategy_missing")
        return ResilienceAssessment(
            meets_rpo=True,
            meets_rto=True,
            continuity_controls_ready=not reasons,
            reasons=reasons,
        )
