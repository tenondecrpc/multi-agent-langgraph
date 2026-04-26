import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.api_deprecations import ApiDeprecation
from backend.app import create_app
from backend.persistence import build_in_memory_persistence
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
    assert "/api/v1/metering/exports/v1" in paths
    assert "/api/v1/metering/exports/v2" in paths


def test_versioned_openapi_document_only_exposes_active_major() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["version"] == "v1"
    assert "/api/v1/webhooks/jira" in payload["paths"]
    assert all(path.startswith("/api/v1") for path in payload["paths"])


def test_unversioned_public_paths_redirect_to_current_major() -> None:
    client = TestClient(create_app(), follow_redirects=False)

    response = client.get("/admin/profile")

    assert response.status_code == 307
    assert response.headers["location"].endswith("/api/v1/admin/profile")


def test_accept_version_negotiates_supported_major_and_rejects_unknown_major() -> None:
    client = TestClient(create_app())

    accepted = client.get("/api/v1/admin/profile", headers={"Accept-Version": "1"})
    rejected = client.get("/api/v1/admin/profile", headers={"Accept-Version": "2"})

    assert accepted.status_code == 200
    assert accepted.headers["x-api-version"] == "v1"
    assert rejected.status_code == 406
    assert rejected.json()["detail"] == "unsupported_api_version"


def test_sse_stream_announces_schema_version_first() -> None:
    client = TestClient(create_app())

    with client.stream("GET", "/api/v1/streams/runs", headers={"Accept-Version": "v1"}) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert body.startswith("event: schema_version\n")
    assert 'data: {"version": "v1"}' in body
    assert "event: ping" in body


def test_admin_api_deprecations_returns_sunset_timeline() -> None:
    deprecations = (
        ApiDeprecation(
            deprecation_id="runs-v1",
            route="/api/v1/runs/{run_id}",
            method="GET",
            version="v1",
            deprecated_at=datetime(2026, 4, 26, tzinfo=UTC),
            sunset_at=datetime(2027, 4, 26, tzinfo=UTC),
            rationale="v2 returns a richer run state envelope.",
            replacement_route="/api/v2/runs/{run_id}",
        ),
    )
    client = TestClient(create_app(api_deprecations=deprecations))

    response = client.get("/api/v1/admin/api-deprecations")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["deprecation_id"] == "runs-v1"
    assert payload[0]["sunset_at"].startswith("2027-04-26")


def test_deprecated_route_emits_headers_and_deprecation_metric() -> None:
    sunset_at = datetime.now(tz=UTC) + timedelta(days=365)
    deprecations = (
        ApiDeprecation(
            deprecation_id="runs-v1",
            route="/api/v1/runs/{run_id}",
            method="GET",
            version="v1",
            deprecated_at=datetime.now(tz=UTC),
            sunset_at=sunset_at,
            rationale="v2 returns a richer run state envelope.",
            replacement_route="/api/v2/runs/{run_id}",
        ),
    )
    client = TestClient(create_app(api_deprecations=deprecations))

    response = client.get(
        "/api/v1/runs/run-1",
        headers={"X-Tenant-ID": "tenant-alpha", "X-Client-ID": "client-a"},
    )
    metrics = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert response.headers["sunset"] == sunset_at.date().isoformat()
    assert response.headers["link"] == '</api/v2/runs/{run_id}>; rel="successor-version"'
    assert (
        'devsquad_api_deprecation_hits_total{route="/api/v1/runs/{run_id}",tenant_id="tenant-alpha",version="v1"} 1.0'
        in metrics.text
    )
    assert 'devsquad_api_deprecation_sunset_days{route="/api/v1/runs/{run_id}",version="v1"}' in metrics.text


def test_metering_export_versions_are_listed_and_served_in_parallel() -> None:
    client = TestClient(create_app())
    period_start = datetime(2026, 4, 26, tzinfo=UTC).isoformat()
    period_end = datetime(2026, 4, 27, tzinfo=UTC).isoformat()

    listed = client.get("/api/v1/metering/exports")
    exported = client.get(
        "/api/v1/metering/exports/v2",
        params={
            "tenant_id": "tenant-alpha",
            "period_start": period_start,
            "period_end": period_end,
            "format": "csv",
        },
    )

    assert listed.status_code == 200
    assert [item["schema_version"] for item in listed.json()["exports"]] == ["v1", "v2"]
    assert all(item["minimum_parallel_support"] == "P12M" for item in listed.json()["exports"])
    assert exported.status_code == 200
    assert exported.headers["x-metering-export-schema"] == "v2"
    assert exported.headers["x-minimum-parallel-support"] == "P12M"
    assert exported.text.startswith("schema_version,")


def test_jira_webhook_route_uses_guard_and_deduplicates_duplicate_deliveries() -> None:
    persistence = build_in_memory_persistence()
    client = TestClient(create_app(persistence=persistence))
    timestamp = int(datetime.now(tz=UTC).timestamp())
    payload = {
        "event_id": "evt-1",
        "ticket_key": "ENG-1",
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "summary": "Implement webhook persistence",
    }
    body = json.dumps(payload)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": persistence.webhook_guard.sign(body, timestamp),
        "X-Atlassian-Webhook-Timestamp": str(timestamp),
    }

    accepted = client.post("/api/v1/webhooks/jira", content=body, headers=headers)
    duplicate = client.post("/api/v1/webhooks/jira", content=body, headers=headers)

    assert accepted.status_code == 200
    assert accepted.json()["deduplicated"] is False
    assert duplicate.status_code == 200
    assert duplicate.json()["deduplicated"] is True
    assert duplicate.headers["x-webhook-deduplicated"] == "true"


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
