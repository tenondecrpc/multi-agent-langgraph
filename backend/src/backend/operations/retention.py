from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field


class DataCategory(StrEnum):
    CHECKPOINTS = "checkpoints"
    MEMORY = "memory"
    METERING = "metering"
    AUDIT = "audit"
    DLQ = "dlq"


class RetentionPolicy(BaseModel):
    category: DataCategory
    retention_days: int
    protect_while_snapshot_pinned: bool = False
    protect_while_incident_open: bool = False


class StoredRecord(BaseModel):
    record_id: str
    category: DataCategory
    tenant_id: str
    created_at: datetime
    snapshot_pinned: bool = False
    incident_open: bool = False


class DeletionActionPlan(BaseModel):
    tenant_id: str
    cascade_order: list[DataCategory]


class ComplianceEvidence(BaseModel):
    action_id: str
    tenant_id: str
    deleted_record_ids: list[str] = Field(default_factory=list)
    retained_reasons: dict[str, str] = Field(default_factory=dict)


class RetentionService:
    def should_delete(
        self,
        record: StoredRecord,
        *,
        policy: RetentionPolicy,
        now: datetime,
    ) -> tuple[bool, str | None]:
        if policy.protect_while_snapshot_pinned and record.snapshot_pinned:
            return False, "snapshot_pinned"
        if policy.protect_while_incident_open and record.incident_open:
            return False, "incident_open"
        expires_at = record.created_at + timedelta(days=policy.retention_days)
        if now >= expires_at:
            return True, None
        return False, "within_retention"

    def execute_cleanup(
        self,
        *,
        tenant_id: str,
        records: list[StoredRecord],
        policies: dict[DataCategory, RetentionPolicy],
        now: datetime | None = None,
    ) -> ComplianceEvidence:
        evaluation_time = now or datetime.now(tz=UTC)
        evidence = ComplianceEvidence(action_id="cleanup", tenant_id=tenant_id)
        for record in records:
            if record.tenant_id != tenant_id:
                continue
            delete, reason = self.should_delete(
                record,
                policy=policies[record.category],
                now=evaluation_time,
            )
            if delete:
                evidence.deleted_record_ids.append(record.record_id)
            elif reason is not None:
                evidence.retained_reasons[record.record_id] = reason
        return evidence

    def plan_tenant_deletion(self, tenant_id: str) -> DeletionActionPlan:
        return DeletionActionPlan(
            tenant_id=tenant_id,
            cascade_order=[
                DataCategory.DLQ,
                DataCategory.CHECKPOINTS,
                DataCategory.MEMORY,
                DataCategory.METERING,
                DataCategory.AUDIT,
            ],
        )
