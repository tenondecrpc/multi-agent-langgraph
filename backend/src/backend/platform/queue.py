from __future__ import annotations

from pydantic import BaseModel


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
    job_id: str
    tenant_id: str
    team_id: str
    run_id: str
    queue_name: str
    failure_reason: str
    checkpoint_ref: str | None = None


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


class InMemoryWorkerController:
    def __init__(self) -> None:
        self.active_jobs: dict[str, QueuedJob] = {}
        self.draining_workers: set[str] = set()
        self.dead_letter_records: list[DeadLetterRecord] = []

    def assign(self, worker_id: str, job: QueuedJob) -> None:
        if worker_id in self.draining_workers:
            raise ValueError(f"Worker `{worker_id}` is draining and cannot accept new jobs.")
        self.active_jobs[worker_id] = job

    def begin_drain(self, worker_id: str) -> WorkerDrainLease:
        self.draining_workers.add(worker_id)
        active_job = self.active_jobs.get(worker_id)
        return WorkerDrainLease(
            worker_id=worker_id,
            accepting_new_jobs=False,
            active_job_id=active_job.job_id if active_job else None,
        )

    def checkpoint_and_release(self, worker_id: str, checkpoint_ref: str) -> QueuedJob:
        active_job = self.active_jobs.pop(worker_id)
        active_job.checkpoint_ref = checkpoint_ref
        return active_job

    def capture_terminal_failure(self, worker_id: str, failure_reason: str) -> DeadLetterRecord:
        active_job = self.active_jobs.pop(worker_id)
        record = DeadLetterRecord(
            job_id=active_job.job_id,
            tenant_id=active_job.tenant_id,
            team_id=active_job.team_id,
            run_id=active_job.run_id,
            queue_name=active_job.queue_name,
            failure_reason=failure_reason,
            checkpoint_ref=active_job.checkpoint_ref,
        )
        self.dead_letter_records.append(record)
        return record
