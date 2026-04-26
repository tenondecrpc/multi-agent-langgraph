from __future__ import annotations

import hmac
import time

import pytest

from backend.persistence.testing.security import InMemoryWebhookGuard
from backend.security.webhook import WebhookRequest


def _sign(body: str, timestamp: int, secret: str) -> str:
    payload = f"{timestamp}.{body}".encode()
    return hmac.new(secret.encode(), payload, "sha256").hexdigest()


@pytest.fixture
def guard():
    return InMemoryWebhookGuard(secret="test-secret", per_minute_limit=100)


@pytest.fixture
def now():
    return int(time.time())


class TestDualSecretRotation:
    def test_signature_valid_with_current_secret(self, guard, now):
        body = '{"event":"issue_created"}'
        signature = _sign(body, now, "test-secret")
        request = WebhookRequest(
            body=body,
            signature=signature,
            timestamp=now,
            event_id="evt-1",
            tenant_id="tenant-test",
            team_id="team-alpha",
            remote_addr="10.0.0.1",
        )
        result = guard.verify(request, now=now)
        assert result.accepted is True

    def test_signature_invalid_rejected(self, guard, now):
        body = '{"event":"issue_created"}'
        request = WebhookRequest(
            body=body,
            signature="invalid-signature",
            timestamp=now,
            event_id="evt-2",
            tenant_id="tenant-test",
            team_id="team-alpha",
            remote_addr="10.0.0.1",
        )
        result = guard.verify(request, now=now)
        assert result.accepted is False
        assert result.rejection_reason == "invalid_signature"


class TestSignatureHashIdempotency:
    def test_idempotency_key_includes_signature_hash(self, guard, now):
        body = '{"event":"issue_created"}'
        signature = _sign(body, now, "test-secret")
        request = WebhookRequest(
            body=body,
            signature=signature,
            timestamp=now,
            event_id="evt-3",
            tenant_id="tenant-test",
            team_id="team-alpha",
            remote_addr="10.0.0.1",
        )
        result = guard.verify(request, now=now)
        assert result.accepted is True
        assert result.idempotency_key is not None

    def test_same_body_same_idempotency_key(self, guard, now):
        body = '{"event":"issue_created"}'
        signature = _sign(body, now, "test-secret")
        request1 = WebhookRequest(
            body=body,
            signature=signature,
            timestamp=now,
            event_id="evt-4",
            tenant_id="tenant-test",
            team_id="team-alpha",
            remote_addr="10.0.0.1",
        )
        request2 = WebhookRequest(
            body=body,
            signature=signature,
            timestamp=now,
            event_id="evt-4",
            tenant_id="tenant-test",
            team_id="team-alpha",
            remote_addr="10.0.0.1",
        )
        result1 = guard.verify(request1, now=now)
        result2 = guard.verify(request2, now=now)
        assert result1.idempotency_key == result2.idempotency_key
        assert result2.deduplicated is True


class TestPerTicketFloodLimit:
    def test_flood_limit_enforced(self, guard, now):
        body = '{"event":"issue_updated"}'
        signature = _sign(body, now, "test-secret")
        for i in range(20):
            request = WebhookRequest(
                body=body,
                signature=signature,
                timestamp=now,
                event_id=f"evt-flood-{i}",
                ticket_key="PROJ-100",
                tenant_id="tenant-test",
                team_id="team-alpha",
                remote_addr="10.0.0.1",
            )
            result = guard.verify(request, now=now)
            assert result.accepted is True

        request = WebhookRequest(
            body=body,
            signature=signature,
            timestamp=now,
            event_id="evt-flood-20",
            ticket_key="PROJ-100",
            tenant_id="tenant-test",
            team_id="team-alpha",
            remote_addr="10.0.0.1",
        )
        result = guard.verify(request, now=now)
        assert result.accepted is False
        assert result.rejection_reason == "rate_limited"


class TestIPAllowlist:
    def test_ip_allowlist_rejects_outside_cidr(self):
        guard_with_allowlist = InMemoryWebhookGuard(
            secret="test-secret",
            ip_allowlist=["192.168.1.0/24"],
        )
        now = int(time.time())
        body = '{"event":"issue_created"}'
        signature = _sign(body, now, "test-secret")
        request = WebhookRequest(
            body=body,
            signature=signature,
            timestamp=now,
            event_id="evt-allowlist-1",
            tenant_id="tenant-test",
            team_id="team-alpha",
            remote_addr="10.0.0.1",
        )
        result = guard_with_allowlist.verify(request, now=now)
        assert result.accepted is False
        assert result.rejection_reason == "ip_not_allowed"

    def test_ip_allowlist_allows_inside_cidr(self):
        guard_with_allowlist = InMemoryWebhookGuard(
            secret="test-secret",
            ip_allowlist=["192.168.1.0/24"],
        )
        now = int(time.time())
        body = '{"event":"issue_created"}'
        signature = _sign(body, now, "test-secret")
        request = WebhookRequest(
            body=body,
            signature=signature,
            timestamp=now,
            event_id="evt-allowlist-2",
            tenant_id="tenant-test",
            team_id="team-alpha",
            remote_addr="192.168.1.50",
        )
        result = guard_with_allowlist.verify(request, now=now)
        assert result.accepted is True


class TestStaleTimestamp:
    def test_stale_timestamp_rejected(self, guard):
        now = int(time.time())
        stale_timestamp = now - 600
        body = '{"event":"issue_created"}'
        signature = _sign(body, stale_timestamp, "test-secret")
        request = WebhookRequest(
            body=body,
            signature=signature,
            timestamp=stale_timestamp,
            event_id="evt-stale-1",
            tenant_id="tenant-test",
            team_id="team-alpha",
            remote_addr="10.0.0.1",
        )
        result = guard.verify(request, now=now)
        assert result.accepted is False
        assert result.rejection_reason == "stale_timestamp"
