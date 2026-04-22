from __future__ import annotations

import asyncio
import logging
import os
from contextlib import contextmanager
from typing import Any, Literal, Protocol

from pydantic import BaseModel
from redis.exceptions import RedisError
from sqlalchemy import Engine, create_engine, select, text

from backend.platform.queue import DeadLetterRecord, QueuedJob, WeightedFairDispatcher, WorkerDrainLease

from .contracts import WorkerController
from .db import ALL_TEAMS_SCOPE, ALL_TENANTS_SCOPE, tenant_guc_values
from .redis import RedisSettings, build_redis_client
from .schema import dead_letter_records
from .telemetry import PersistenceTelemetry, bootstrap_telemetry

WORKER_CONTROLLER_MODE_ENV_KEY = "BACKEND_WORKER_CONTROLLER_MODE"
WORKER_QUEUE_NAME_ENV_KEY = "BACKEND_WORKER_QUEUE_NAME"
WORKER_DRAIN_LEASE_TTL_ENV_KEY = "BACKEND_WORKER_DRAIN_LEASE_TTL_SECONDS"
WORKER_PER_TENANT_CONCURRENCY_ENV_KEY = "BACKEND_WORKER_PER_TENANT_CONCURRENCY"
WORKER_STARVATION_THRESHOLD_ENV_KEY = "BACKEND_WORKER_STARVATION_THRESHOLD_SECONDS"
WORKER_ARQ_FUNCTION_ENV_KEY = "BACKEND_WORKER_ARQ_FUNCTION"

_ACTIVE_JOBS_HASH = "worker_controller:active_jobs"
_DRAINING_WORKERS_SET = "worker_controller:draining_workers"
_DRAIN_LEASE_PREFIX = "worker_controller:drain:"
_IN_FLIGHT_PREFIX = "worker_controller:in_flight:"


class RedisLike(Protocol):
    def delete(self, *keys: str) -> int: ...

    def exists(self, key: str) -> int: ...

    def get(self, key: str) -> str | None: ...

    def hdel(self, name: str, *keys: str) -> int: ...

    def hget(self, name: str, key: str) -> str | None: ...

    def hset(self, name: str, key: str, value: str) -> int: ...

    def incrby(self, key: str, amount: int = 1) -> int: ...

    def decrby(self, key: str, amount: int = 1) -> int: ...

    def publish(self, channel: str, message: str) -> int: ...

    def sadd(self, name: str, *values: str) -> int: ...

    def set(self, key: str, value: str, ex: int | None = None) -> bool: ...

    def srem(self, name: str, *values: str) -> int: ...

    def smembers(self, name: str) -> set[str]: ...


class WorkerControllerSettings(BaseModel):
    mode: Literal["legacy", "redis"] = "legacy"
    queue_name: str = "ticket-runs"
    arq_function_name: str = "process_ticket_run"
    drain_lease_ttl_seconds: int = 300
    per_tenant_concurrency: int = 2
    starvation_threshold_seconds: int = 300

    @classmethod
    def from_env(cls) -> WorkerControllerSettings:
        mode = os.getenv(WORKER_CONTROLLER_MODE_ENV_KEY, "legacy")
        if mode not in {"legacy", "redis"}:
            raise ValueError(
                f"{WORKER_CONTROLLER_MODE_ENV_KEY} must be 'legacy' or 'redis', got '{mode}'"
            )
        return cls(
            mode=mode,  # type: ignore[arg-type]
            queue_name=os.getenv(WORKER_QUEUE_NAME_ENV_KEY, "ticket-runs"),
            arq_function_name=os.getenv(WORKER_ARQ_FUNCTION_ENV_KEY, "process_ticket_run"),
            drain_lease_ttl_seconds=int(os.getenv(WORKER_DRAIN_LEASE_TTL_ENV_KEY, "300")),
            per_tenant_concurrency=int(os.getenv(WORKER_PER_TENANT_CONCURRENCY_ENV_KEY, "2")),
            starvation_threshold_seconds=int(os.getenv(WORKER_STARVATION_THRESHOLD_ENV_KEY, "300")),
        )


class ArqQueueTransport:
    def __init__(
        self,
        *,
        redis_settings: RedisSettings,
        queue_name: str,
        function_name: str,
    ) -> None:
        self.redis_settings = redis_settings
        self.queue_name = queue_name
        self.function_name = function_name

    async def enqueue(self, job: QueuedJob):
        from arq import create_pool
        from arq.connections import RedisSettings as ArqRedisSettings

        pool = await create_pool(
            ArqRedisSettings.from_dsn(self.redis_settings.url),
            default_queue_name=self.queue_name,
        )
        try:
            return await pool.enqueue_job(
                self.function_name,
                _job_id=job.job_id,
                _queue_name=job.queue_name,
                tenant_id=job.tenant_id,
                team_id=job.team_id,
                run_id=job.run_id,
                weight=job.weight,
                enqueued_at=job.enqueued_at,
                retry_count=job.retry_count,
                checkpoint_ref=job.checkpoint_ref,
            )
        finally:
            await pool.close(close_connection_pool=True)

    async def queued_jobs(self) -> list[QueuedJob]:
        from arq import create_pool
        from arq.connections import RedisSettings as ArqRedisSettings

        pool = await create_pool(
            ArqRedisSettings.from_dsn(self.redis_settings.url),
            default_queue_name=self.queue_name,
        )
        try:
            jobs = await pool.queued_jobs(queue_name=self.queue_name)
        finally:
            await pool.close(close_connection_pool=True)
        return [
            QueuedJob(
                job_id=job.job_id or "",
                tenant_id=str(job.kwargs["tenant_id"]),
                team_id=str(job.kwargs["team_id"]),
                run_id=str(job.kwargs["run_id"]),
                queue_name=self.queue_name,
                weight=int(job.kwargs.get("weight", 1)),
                enqueued_at=int(job.kwargs["enqueued_at"]),
                retry_count=int(job.kwargs.get("retry_count", 0)),
                checkpoint_ref=job.kwargs.get("checkpoint_ref"),
            )
            for job in jobs
            if job.job_id is not None
        ]


class RedisWorkerController:
    def __init__(
        self,
        database_url: str,
        *,
        redis_settings: RedisSettings | None = None,
        redis_client: RedisLike | None = None,
        engine: Engine | None = None,
        settings: WorkerControllerSettings | None = None,
        logger: logging.Logger | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self.settings = settings or WorkerControllerSettings.from_env()
        self.queue_name = self.settings.queue_name
        self._redis = redis_client or build_redis_client(redis_settings or RedisSettings.from_env())
        self._engine = engine or create_engine(database_url, future=True, pool_pre_ping=True)
        self._logger = logger or logging.getLogger(__name__)
        self._telemetry = telemetry or bootstrap_telemetry()
        self._local_active_jobs: dict[str, QueuedJob] = {}
        self._local_draining_workers: set[str] = set()
        self._dispatcher = WeightedFairDispatcher(
            per_tenant_concurrency=self.settings.per_tenant_concurrency,
            starvation_threshold_seconds=self.settings.starvation_threshold_seconds,
        )
        redis_runtime_settings = redis_settings or RedisSettings.from_env()
        self.queue_transport = ArqQueueTransport(
            redis_settings=redis_runtime_settings,
            queue_name=self.queue_name,
            function_name=self.settings.arq_function_name,
        )

    @property
    def draining_workers(self) -> set[str]:
        try:
            return {str(value) for value in self._redis.smembers(_DRAINING_WORKERS_SET)}
        except RedisError:
            return set(self._local_draining_workers)

    def select_next_job(self, jobs: list[QueuedJob], *, now: int) -> QueuedJob | None:
        with self._telemetry.trace(
            "worker_controller_select_next_job",
            subsystem="worker_controller",
            operation="select_next_job",
        ):
            return self._dispatcher.select_next_job(jobs, self._in_flight_by_tenant(jobs), now)

    def assign(self, worker_id: str, job: QueuedJob) -> None:
        with self._telemetry.trace(
            "worker_controller_assign",
            subsystem="worker_controller",
            operation="assign",
            tenant_id=job.tenant_id,
            team_id=job.team_id,
            run_id=job.run_id,
        ):
            if worker_id in self.draining_workers or self._lease_exists(worker_id):
                raise ValueError(f"Worker `{worker_id}` is draining and cannot accept new jobs.")

            in_flight = self._tenant_in_flight(job.tenant_id)
            if in_flight >= self.settings.per_tenant_concurrency:
                raise ValueError(
                    f"Tenant `{job.tenant_id}` is already at concurrency limit {self.settings.per_tenant_concurrency}."
                )

            self._local_active_jobs[worker_id] = job.model_copy(deep=True)
            try:
                self._redis.hset(_ACTIVE_JOBS_HASH, worker_id, job.model_dump_json())
                self._redis.incrby(_tenant_counter_key(job.tenant_id), 1)
            except RedisError as exc:
                self._local_active_jobs.pop(worker_id, None)
                raise RuntimeError("Redis-backed worker coordination is unavailable.") from exc

    def begin_drain(self, worker_id: str) -> WorkerDrainLease:
        with self._telemetry.trace(
            "worker_controller_begin_drain",
            subsystem="worker_controller",
            operation="begin_drain",
            run_id=worker_id,
        ):
            active_job = self._get_active_job(worker_id)
            self._local_draining_workers.add(worker_id)
            try:
                self._redis.set(
                    _drain_lease_key(worker_id),
                    "1",
                    ex=self.settings.drain_lease_ttl_seconds,
                )
                self._redis.sadd(_DRAINING_WORKERS_SET, worker_id)
            except RedisError as exc:
                raise RuntimeError("Unable to acquire the worker drain lease in Redis.") from exc

            return WorkerDrainLease(
                worker_id=worker_id,
                accepting_new_jobs=False,
                active_job_id=active_job.job_id if active_job else None,
            )

    def checkpoint_and_release(self, worker_id: str, checkpoint_ref: str) -> QueuedJob:
        with self._telemetry.trace(
            "worker_controller_checkpoint_and_release",
            subsystem="worker_controller",
            operation="checkpoint_and_release",
            run_id=worker_id,
        ):
            active_job = self._require_active_job(worker_id)
            released_job = active_job.model_copy(update={"checkpoint_ref": checkpoint_ref})
            self._local_active_jobs.pop(worker_id, None)
            self._local_draining_workers.discard(worker_id)

            try:
                self._redis.hdel(_ACTIVE_JOBS_HASH, worker_id)
                self._redis.decrby(_tenant_counter_key(active_job.tenant_id), 1)
                self._redis.delete(_drain_lease_key(worker_id))
                self._redis.srem(_DRAINING_WORKERS_SET, worker_id)
            except RedisError:
                self._logger.warning(
                    "worker_release_redis_cleanup_failed",
                    extra={"worker_id": worker_id, "job_id": active_job.job_id},
                )

            return released_job

    def capture_terminal_failure(self, worker_id: str, failure_reason: str) -> DeadLetterRecord:
        with self._telemetry.trace(
            "worker_controller_capture_terminal_failure",
            subsystem="worker_controller",
            operation="capture_terminal_failure",
            run_id=worker_id,
        ):
            active_job = self._require_active_job(worker_id)
            record = DeadLetterRecord(
                job_id=active_job.job_id,
                tenant_id=active_job.tenant_id,
                team_id=active_job.team_id,
                run_id=active_job.run_id,
                queue_name=active_job.queue_name,
                worker_id=worker_id,
                failure_reason=failure_reason,
                checkpoint_ref=active_job.checkpoint_ref,
            )
            persisted = self._insert_dead_letter_record(record)

            self._local_active_jobs.pop(worker_id, None)
            self._local_draining_workers.discard(worker_id)
            try:
                self._redis.hdel(_ACTIVE_JOBS_HASH, worker_id)
                self._redis.decrby(_tenant_counter_key(active_job.tenant_id), 1)
                self._redis.delete(_drain_lease_key(worker_id))
                self._redis.srem(_DRAINING_WORKERS_SET, worker_id)
            except RedisError:
                self._logger.warning(
                    "worker_dlq_redis_cleanup_failed",
                    extra={"worker_id": worker_id, "job_id": active_job.job_id},
                )

            return persisted

    def list_dead_letter_records(self) -> list[DeadLetterRecord]:
        with self._telemetry.trace(
            "worker_controller_list_dead_letter_records",
            subsystem="worker_controller",
            operation="list_dead_letter_records",
        ):
            with self._scoped_transaction(ALL_TENANTS_SCOPE, ALL_TEAMS_SCOPE) as connection:
                rows = connection.execute(
                    select(dead_letter_records).order_by(dead_letter_records.c.created_at.asc())
                ).mappings().all()
            return [self._dead_letter_from_row(row) for row in rows]

    def queued_jobs(self) -> list[QueuedJob]:
        with self._telemetry.trace(
            "worker_controller_queued_jobs",
            subsystem="worker_controller",
            operation="queued_jobs",
        ):
            return asyncio.run(self.queue_transport.queued_jobs())

    def _get_active_job(self, worker_id: str) -> QueuedJob | None:
        job = self._local_active_jobs.get(worker_id)
        if job is not None:
            return job
        try:
            raw_job = self._redis.hget(_ACTIVE_JOBS_HASH, worker_id)
        except RedisError:
            return None
        if raw_job is None:
            return None
        job = QueuedJob.model_validate_json(raw_job)
        self._local_active_jobs[worker_id] = job
        return job

    def _require_active_job(self, worker_id: str) -> QueuedJob:
        job = self._get_active_job(worker_id)
        if job is None:
            raise KeyError(f"No active job is registered for worker `{worker_id}`.")
        return job

    def _tenant_in_flight(self, tenant_id: str) -> int:
        try:
            raw_value = self._redis.get(_tenant_counter_key(tenant_id))
        except RedisError:
            return sum(1 for job in self._local_active_jobs.values() if job.tenant_id == tenant_id)
        return int(raw_value or 0)

    def _in_flight_by_tenant(self, jobs: list[QueuedJob]) -> dict[str, int]:
        tenant_ids = {job.tenant_id for job in jobs}
        return {tenant_id: self._tenant_in_flight(tenant_id) for tenant_id in tenant_ids}

    def _lease_exists(self, worker_id: str) -> bool:
        try:
            return bool(self._redis.exists(_drain_lease_key(worker_id)))
        except RedisError:
            return worker_id in self._local_draining_workers

    def _insert_dead_letter_record(self, record: DeadLetterRecord) -> DeadLetterRecord:
        with self._scoped_transaction(record.tenant_id, record.team_id) as connection:
            row = connection.execute(
                text(
                    """
                    INSERT INTO dead_letter_records (
                        job_id,
                        tenant_id,
                        team_id,
                        run_id,
                        queue_name,
                        worker_id,
                        failure_reason,
                        checkpoint_ref
                    ) VALUES (
                        :job_id,
                        :tenant_id,
                        :team_id,
                        :run_id,
                        :queue_name,
                        :worker_id,
                        :failure_reason,
                        :checkpoint_ref
                    )
                    RETURNING id, job_id, tenant_id, team_id, run_id, queue_name,
                              worker_id, failure_reason, checkpoint_ref, created_at
                    """
                ),
                record.model_dump(),
            ).mappings().one()
        return self._dead_letter_from_row(row)

    @contextmanager
    def _scoped_transaction(self, tenant_id: str, team_id: str):
        with self._engine.begin() as connection:
            for key, value in tenant_guc_values(tenant_id=tenant_id, team_id=team_id).items():
                connection.execute(
                    text("SELECT set_config(:key, :value, true)"),
                    {"key": key, "value": value},
                )
            yield connection

    def _dead_letter_from_row(self, row: Any) -> DeadLetterRecord:
        return DeadLetterRecord(
            record_id=str(row["id"]),
            job_id=row["job_id"],
            tenant_id=row["tenant_id"],
            team_id=row["team_id"],
            run_id=row["run_id"],
            queue_name=row["queue_name"],
            worker_id=row["worker_id"],
            failure_reason=row["failure_reason"],
            checkpoint_ref=row["checkpoint_ref"],
            created_at=row["created_at"],
        )


def build_worker_controller(
    *,
    database_url: str | None,
    redis_settings: RedisSettings,
    legacy_controller: WorkerController | None,
    settings: WorkerControllerSettings | None = None,
    logger: logging.Logger | None = None,
    telemetry: PersistenceTelemetry | None = None,
) -> WorkerController:
    resolved = settings or WorkerControllerSettings.from_env()
    if resolved.mode == "legacy":
        if legacy_controller is None:
            raise RuntimeError("Legacy worker-controller mode requires an in-memory test double.")
        return legacy_controller
    if not database_url:
        raise RuntimeError(
            f"{WORKER_CONTROLLER_MODE_ENV_KEY}=redis requires a configured database URL"
        )
    if not redis_settings.configured:
        raise RuntimeError(
            f"{WORKER_CONTROLLER_MODE_ENV_KEY}=redis requires a configured Redis URL"
        )
    return RedisWorkerController(
        database_url,
        redis_settings=redis_settings,
        settings=resolved,
        logger=logger,
        telemetry=telemetry,
    )


def _tenant_counter_key(tenant_id: str) -> str:
    return f"{_IN_FLIGHT_PREFIX}{tenant_id}"


def _drain_lease_key(worker_id: str) -> str:
    return f"{_DRAIN_LEASE_PREFIX}{worker_id}"
