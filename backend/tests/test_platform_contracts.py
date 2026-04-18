from fastapi.testclient import TestClient

from backend.app import create_app
from backend.platform import InMemoryWorkerController, QueuedJob, SandboxTemplateBuilder, WeightedFairDispatcher


def test_openapi_exposes_versioned_platform_route_groups() -> None:
    client = TestClient(create_app())
    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]

    assert "/api/v1/webhooks/jira" in paths
    assert "/api/v1/runs/{run_id}" in paths
    assert "/api/v1/streams/runs" in paths
    assert "/api/v1/auth/callback" in paths
    assert "/api/v1/admin/profile" in paths
    assert "/api/v1/metering/exports" in paths


def test_weighted_fair_dispatcher_prioritizes_starved_jobs_and_respects_caps() -> None:
    dispatcher = WeightedFairDispatcher(per_tenant_concurrency=1, starvation_threshold_seconds=300)
    jobs = [
        QueuedJob(
            job_id="job-b",
            tenant_id="tenant-b",
            team_id="team-b",
            run_id="run-b",
            enqueued_at=10,
        ),
        QueuedJob(
            job_id="job-a",
            tenant_id="tenant-a",
            team_id="team-a",
            run_id="run-a",
            enqueued_at=0,
        ),
    ]

    selected = dispatcher.select_next_job(jobs, {"tenant-b": 1}, now=400)
    assert selected is not None
    assert selected.job_id == "job-a"


def test_worker_drain_preserves_checkpoint_and_dlq_capture() -> None:
    controller = InMemoryWorkerController()
    job = QueuedJob(
        job_id="job-1",
        tenant_id="tenant-alpha",
        team_id="team-core",
        run_id="run-1",
        enqueued_at=1,
    )
    controller.assign("worker-1", job)

    lease = controller.begin_drain("worker-1")
    assert lease.accepting_new_jobs is False
    assert lease.active_job_id == "job-1"

    checkpointed = controller.checkpoint_and_release("worker-1", checkpoint_ref="checkpoint-1")
    assert checkpointed.checkpoint_ref == "checkpoint-1"

    controller.assign("worker-2", checkpointed)
    record = controller.capture_terminal_failure("worker-2", failure_reason="retry_budget_exhausted")
    assert record.checkpoint_ref == "checkpoint-1"
    assert record.failure_reason == "retry_budget_exhausted"


def test_sandbox_templates_are_tenant_scoped_and_non_root() -> None:
    builder = SandboxTemplateBuilder()
    primary = builder.build(
        tenant_id="tenant-alpha",
        team_id="team-core",
        run_id="run-1",
        worker_pool="primary",
    )
    shadow = builder.build(
        tenant_id="tenant-alpha",
        team_id="team-core",
        run_id="run-1",
        worker_pool="shadow",
    )

    assert primary.namespace == "tenant-tenant-alpha"
    assert primary.runtime_class_name == "runsc"
    assert primary.run_as_non_root is True
    assert primary.worker_pool.read_only is False

    assert shadow.worker_pool.read_only is True
    assert shadow.read_only_root_filesystem is True
    assert shadow.worker_pool.queue_name != primary.worker_pool.queue_name
