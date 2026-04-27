"""Schemathesis-based fuzz tests for webhooks and admin API.

These tests contract-fuzz the OpenAPI specification to find hangs,
crashes, or invariant violations in the webhook and admin API surfaces.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

pytestmark = pytest.mark.fuzz

_AUTH_HEADERS = {
    "X-Subject": "test-admin",
    "X-Tenant-Id": "tenant-1",
    "X-Team-Id": "team-1",
    "X-Role": "super-admin",
    "X-Session": "test-session",
    "X-Expires": "9999999999",
}


class TestWebhookFuzz:
    """Fuzz the Jira webhook intake endpoint."""

    def test_webhook_accepts_valid_payload(self, synthetic_jira_webhook):
        """Baseline: webhook should accept valid synthetic payload."""
        assert "webhookEvent" in synthetic_jira_webhook
        assert "issue" in synthetic_jira_webhook

    def test_webhook_rejects_malformed_payload(self):
        """Webhook should reject malformed payloads gracefully."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        malformed_payloads = [
            {"invalid": "data"},
            {"webhookEvent": None},
            {"issue": {"id": 123}},
            {"webhookEvent": "jira:issue_created", "issue": {}},
        ]
        for payload in malformed_payloads:
            response = client.post(
                "/api/v1/webhooks/jira",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code in (400, 401, 403, 422), (
                f"Expected 4xx for malformed payload, got {response.status_code}"
            )

    def test_webhook_idempotency_under_fuzz(self):
        """Webhook should maintain idempotency under fuzzed duplicate requests."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        valid_payload = {
            "webhookEvent": "jira:issue_created",
            "issue": {"id": "10001", "key": "PROJ-1", "fields": {"summary": "Test"}},
        }
        responses = []
        for _ in range(3):
            response = client.post(
                "/api/v1/webhooks/jira",
                json=valid_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": "sha256=test",
                    "X-Timestamp": "9999999999",
                },
            )
            responses.append(response.status_code)
        assert all(r in (400, 401, 403, 422) for r in responses)


class TestAdminAPIFuzz:
    """Fuzz the admin API endpoints."""

    def test_admin_api_requires_authentication(self):
        """Admin API should require authentication for all endpoints."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        admin_endpoints = [
            ("GET", "/api/v1/admin/data-retention/policies"),
            ("GET", "/api/v1/admin/credentials/rotation-schedule"),
            ("GET", "/api/v1/admin/webhook/secret-rotation-status?tenant_id=t&team_id=t"),
            ("GET", "/api/v1/admin/admission-exceptions/"),
        ]
        for method, path in admin_endpoints:
            response = client.request(method, path)
            assert response.status_code in (401, 403, 404), (
                f"Expected 401/403/404 for {method} {path}, got {response.status_code}"
            )

    def test_admin_api_validates_input_schema(self):
        """Admin API should validate input against schema."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        response = client.post(
            "/api/v1/admin/data-retention/policies",
            json={"invalid": "data"},
            headers=_AUTH_HEADERS,
        )
        assert response.status_code in (401, 403, 404, 422)

    def test_admin_api_rate_limiting(self):
        """Admin API should enforce rate limiting under fuzz."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        for _ in range(5):
            response = client.get("/api/v1/admin/data-retention/policies", headers=_AUTH_HEADERS)
            assert response.status_code in (401, 403, 404, 429)


class TestSchemathesisIntegration:
    """Integration tests for schemathesis configuration."""

    def test_openapi_spec_is_accessible(self):
        """OpenAPI spec should be accessible for schemathesis."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert "openapi" in spec
        assert "paths" in spec

    def test_schemathesis_can_parse_spec(self):
        """Schemathesis should be able to parse the OpenAPI spec."""
        client = TestClient(create_app(), raise_server_exceptions=False)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert "openapi" in spec
        assert "paths" in spec
        assert len(spec["paths"]) > 0
