from fastapi.testclient import TestClient

from backend.app import create_app


def test_health_endpoints_report_ready() -> None:
    client = TestClient(create_app())

    health = client.get("/healthz")
    ready = client.get("/readyz")
    metrics = client.get("/metrics")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert "persistence" in health.json()

    assert ready.status_code == 200
    assert ready.json()["status"] == "ok"
    assert "persistence" in ready.json()

    assert metrics.status_code == 200
    assert "devsquad_database_pool_utilisation_ratio" in metrics.text
    assert "devsquad_persistence_migration_info" in metrics.text


def test_simulate_runtime_flow_returns_completed_run() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/runtime/simulate",
        json={
            "planning": {
                "summary": "Add runtime backbone coverage",
                "ticket_key": "ENG-42",
                "implementation_tasks": ["Implement runtime workflow nodes"],
            },
            "execution": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticket_key"] == "ENG-42"
    assert payload["pr_created"] is True
    assert payload["status"] == "completed"
    assert payload["node_history"] == [
        "intake",
        "load_constitution",
        "create_feature_spec",
        "clarify",
        "create_plan",
        "create_task_list",
        "readiness_gate",
        "coder",
        "tester",
        "reviewer",
        "pre_pr_sync",
        "pr_creator",
    ]


def test_simulate_runtime_flow_accepts_ticket_id_alias() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/runtime/simulate",
        json={
            "planning": {
                "summary": "Add runtime backbone coverage",
                "ticket_id": "PROJ-1",
                "implementation_tasks": ["Implement runtime workflow nodes"],
            },
            "execution": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticket_key"] == "PROJ-1"
    assert payload["thread_id"].startswith("tenant-alpha:PROJ-1:")


def test_simulate_runtime_flow_rejects_conflicting_ticket_identifiers() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/runtime/simulate",
        json={
            "planning": {
                "summary": "Add runtime backbone coverage",
                "ticket_key": "ENG-42",
                "ticket_id": "PROJ-1",
                "implementation_tasks": ["Implement runtime workflow nodes"],
            },
            "execution": {},
        },
    )

    assert response.status_code == 422
    assert "ticket_key" in response.text
    assert "ticket_id" in response.text
