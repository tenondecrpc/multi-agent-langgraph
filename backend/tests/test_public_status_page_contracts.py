from fastapi.testclient import TestClient

from backend.app import create_app
from backend.persistence import build_in_memory_persistence


def test_public_status_page_uses_whitelist_schema() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/status-page")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"schema_version", "generated_at", "status", "components"}
    assert payload["schema_version"] == "public-status.v1"
    assert payload["status"] in {"operational", "degraded", "partial_outage", "major_outage"}

    expected_components = {
        "api",
        "workers",
        "database",
        "redis",
        "provider_routing",
        "sandbox_runtime",
        "persistence_backbone",
    }
    components = payload["components"]
    assert {item["component"] for item in components} == expected_components
    for component in components:
        assert set(component) == {"component", "status", "message"}
        assert component["status"] in {"operational", "degraded", "partial_outage", "major_outage"}
        assert component["message"]


def test_public_status_page_does_not_expose_customer_or_ticket_data() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/status-page",
        headers={
            "X-Tenant-ID": "tenant-alpha",
            "X-Team-ID": "team-core",
            "X-Ticket-Key": "PROJ-1",
        },
    )

    assert response.status_code == 200
    rendered = response.text.lower()
    for forbidden in {
        "tenant",
        "team",
        "ticket",
        "proj-1",
        "tenant-alpha",
        "team-core",
        "secret",
        "token",
    }:
        assert forbidden not in rendered


def test_public_status_page_reflects_prometheus_backed_degradation() -> None:
    persistence = build_in_memory_persistence()
    persistence.telemetry.set_gauge("devsquad_dlq_depth", 150.0)
    persistence.telemetry.set_gauge("devsquad_provider_circuit_breaker_state", 2.0, provider_id="llm-a")
    client = TestClient(create_app(persistence=persistence))

    response = client.get("/api/v1/status-page")

    assert response.status_code == 200
    payload = response.json()
    components = {item["component"]: item for item in payload["components"]}
    assert components["workers"]["status"] == "partial_outage"
    assert components["provider_routing"]["status"] == "partial_outage"
    assert payload["status"] in {"partial_outage", "major_outage"}
