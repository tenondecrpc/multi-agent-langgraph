from __future__ import annotations

from backend.platform.queue import DeadLetterRecord, QueuedJob, WorkerDrainLease


class InMemoryWorkerController:
    def __init__(self) -> None:
        self.queue_name = "ticket-runs"
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

    def select_next_job(self, jobs: list[QueuedJob], *, now: int) -> QueuedJob | None:
        in_flight_by_tenant: dict[str, int] = {}
        for job in self.active_jobs.values():
            in_flight_by_tenant[job.tenant_id] = in_flight_by_tenant.get(job.tenant_id, 0) + 1
        from backend.platform.queue import WeightedFairDispatcher

        dispatcher = WeightedFairDispatcher()
        return dispatcher.select_next_job(jobs, in_flight_by_tenant, now)
