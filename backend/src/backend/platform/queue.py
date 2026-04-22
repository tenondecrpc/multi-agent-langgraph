from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.persistence.testing.worker import InMemoryWorkerController


class QueuedJob(BaseModel):
    job_id: str
    tenant_id: str
    team_id: str
    run_id: str
    queue_name: str = "ticket-runs"
    weight: int = 1
    enqueued_at: int
    retry_count: int = 0
    checkpoint_ref: str | None = None


class WorkerDrainLease(BaseModel):
    worker_id: str
    accepting_new_jobs: bool
    active_job_id: str | None = None


class DeadLetterRecord(BaseModel):
    record_id: str | None = None
    job_id: str
    tenant_id: str
    team_id: str
    run_id: str
    queue_name: str
    failure_reason: str
    worker_id: str | None = None
    checkpoint_ref: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class WeightedFairDispatcher:
    def __init__(self, *, per_tenant_concurrency: int = 2, starvation_threshold_seconds: int = 300) -> None:
        self.per_tenant_concurrency = per_tenant_concurrency
        self.starvation_threshold_seconds = starvation_threshold_seconds

    def select_next_job(
        self, jobs: list[QueuedJob], in_flight_by_tenant: dict[str, int], now: int
    ) -> QueuedJob | None:
        eligible = [
            job
            for job in jobs
            if in_flight_by_tenant.get(job.tenant_id, 0) < self.per_tenant_concurrency
        ]
        if not eligible:
            return None

        starved = [
            job for job in eligible if (now - job.enqueued_at) >= self.starvation_threshold_seconds
        ]
        if starved:
            return min(starved, key=lambda job: job.enqueued_at)

        return min(
            eligible,
            key=lambda job: (
                in_flight_by_tenant.get(job.tenant_id, 0) / max(job.weight, 1),
                job.enqueued_at,
            ),
        )


__all__ = [
    "DeadLetterRecord",
    "InMemoryWorkerController",
    "QueuedJob",
    "WeightedFairDispatcher",
    "WorkerDrainLease",
]


def __getattr__(name: str):
    if name == "InMemoryWorkerController":
        from backend.persistence.testing.worker import InMemoryWorkerController

        return InMemoryWorkerController
    raise AttributeError(name)
