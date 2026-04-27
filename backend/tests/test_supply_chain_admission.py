"""Tests for supply-chain admission exceptions API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app import create_app

_AUTH_HEADERS = {
    "X-Subject": "test-admin",
    "X-Tenant-Id": "tenant-1",
    "X-Team-Id": "team-1",
    "X-Role": "super-admin",
    "X-Session": "test-session",
    "X-Expires": "9999999999",
}


def _client() -> TestClient:
    return TestClient(create_app())


class TestAdmissionExceptionCreate:
    def test_create_exception_succeeds_with_valid_input(self) -> None:
        future = datetime.now(UTC) + timedelta(days=7)
        response = _client().post(
            "/api/v1/admin/admission-exceptions/",
            json={
                "tenant_id": "tenant-1",
                "team_id": "team-1",
                "policy_name": "require-image-signature",
                "image_reference": "ghcr.io/dev-squad/backend:abc123",
                "rationale": "Emergency deployment while CI pipeline is repaired",
                "approved_by": "admin-1",
                "second_approver": "admin-2",
                "expires_at": future.isoformat(),
            },
            headers=_AUTH_HEADERS,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exception_id"].startswith("exc-")
        assert data["tenant_id"] == "tenant-1"
        assert data["policy_name"] == "require-image-signature"
        assert data["approved_by"] == "admin-1"
        assert data["second_approver"] == "admin-2"
        assert data["revoked_at"] is None

    def test_create_exception_rejects_past_expiry(self) -> None:
        past = datetime.now(UTC) - timedelta(days=1)
        response = _client().post(
            "/api/v1/admin/admission-exceptions/",
            json={
                "tenant_id": "tenant-1",
                "team_id": "team-1",
                "policy_name": "require-image-signature",
                "image_reference": "ghcr.io/dev-squad/backend:abc123",
                "rationale": "Test",
                "approved_by": "admin-1",
                "second_approver": "admin-2",
                "expires_at": past.isoformat(),
            },
            headers=_AUTH_HEADERS,
        )
        assert response.status_code == 400
        assert "expires_at must be in the future" in response.json()["detail"]

    def test_create_exception_rejects_same_approver_and_second_approver(self) -> None:
        future = datetime.now(UTC) + timedelta(days=7)
        response = _client().post(
            "/api/v1/admin/admission-exceptions/",
            json={
                "tenant_id": "tenant-1",
                "team_id": "team-1",
                "policy_name": "require-image-signature",
                "image_reference": "ghcr.io/dev-squad/backend:abc123",
                "rationale": "Test",
                "approved_by": "admin-1",
                "second_approver": "admin-1",
                "expires_at": future.isoformat(),
            },
            headers=_AUTH_HEADERS,
        )
        assert response.status_code == 400
        assert "second_approver must be different" in response.json()["detail"]


class TestAdmissionExceptionList:
    def test_list_exceptions_returns_empty_by_default(self) -> None:
        response = _client().get("/api/v1/admin/admission-exceptions/", headers=_AUTH_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["exceptions"] == []
        assert data["total"] == 0

    def test_list_exceptions_filters_by_tenant(self) -> None:
        response = _client().get(
            "/api/v1/admin/admission-exceptions/",
            params={"tenant_id": "tenant-1"},
            headers=_AUTH_HEADERS,
        )
        assert response.status_code == 200


class TestAdmissionExceptionGet:
    def test_get_nonexistent_exception_returns_404(self) -> None:
        response = _client().get("/api/v1/admin/admission-exceptions/exc-nonexistent", headers=_AUTH_HEADERS)
        assert response.status_code == 404


class TestAdmissionExceptionRevoke:
    def test_revoke_nonexistent_exception_returns_404(self) -> None:
        response = _client().post(
            "/api/v1/admin/admission-exceptions/exc-nonexistent/revoke",
            json={"revoked_by": "admin-1", "revoke_reason": "test"},
            headers=_AUTH_HEADERS,
        )
        assert response.status_code == 404


class TestAdmissionExceptionDelete:
    def test_delete_nonexistent_exception_returns_404(self) -> None:
        response = _client().delete("/api/v1/admin/admission-exceptions/exc-nonexistent", headers=_AUTH_HEADERS)
        assert response.status_code == 404
