from __future__ import annotations

import logging

import pytest

from backend.persistence.factory import build_persistence_adapters
from backend.persistence.testing.security import InMemoryWebhookGuard
from backend.persistence.webhook import (
    PostgresRedisWebhookGuard,
    ShadowWebhookGuard,
)
from backend.security.webhook import WebhookGuardResult, WebhookRequest


class RecordingStore:
    def __init__(self) -> None:
        self.insert_calls = 0

    def insert_delivery(
        self,
        request: WebhookRequest,
        *,
        disposition_status: str,
        signature_hash: str | None = None,
    ) -> bool:
        self.insert_calls += 1
        return True


class RecordingCache:
    def __init__(self) -> None:
        self.seen_calls = 0
        self.remember_calls = 0

    def seen(self, key: str) -> bool:
        self.seen_calls += 1
        return False

    def remember(self, key: str, *, ttl_seconds: int) -> None:
        self.remember_calls += 1


class CandidateMismatchGuard:
    def verify(self, request: WebhookRequest, *, now: int) -> WebhookGuardResult:
        return WebhookGuardResult(
            accepted=True,
            deduplicated=False,
            idempotency_key=f"candidate:{request.event_id}",
        )

    def sign(self, body: str, timestamp: int) -> str:
        return ""


def test_postgres_redis_webhook_guard_checks_freshness_before_cache_or_database() -> None:
    store = RecordingStore()
    cache = RecordingCache()
    guard = PostgresRedisWebhookGuard(
        secret="shared-secret",
        record_store=store,
        dedupe_cache=cache,
        freshness_window_seconds=300,
    )
    stale_request = WebhookRequest(
        body='{"ticket":"ENG-1"}',
        signature="",
        timestamp=10,
        event_id="evt-1",
        tenant_id="tenant-alpha",
        team_id="team-core",
        remote_addr="10.0.0.1",
    )
    stale_request.signature = guard.sign(stale_request.body, stale_request.timestamp)

    result = guard.verify(stale_request, now=1_000)

    assert result.rejection_reason == "stale_timestamp"
    assert store.insert_calls == 0
    assert cache.seen_calls == 0
    assert cache.remember_calls == 0


def test_shadow_webhook_guard_logs_mismatch_without_affecting_baseline(caplog: pytest.LogCaptureFixture) -> None:
    baseline = InMemoryWebhookGuard(secret="shared-secret")
    request = WebhookRequest(
        body='{"ticket":"ENG-1"}',
        signature="",
        timestamp=1_000,
        event_id="evt-1",
        tenant_id="tenant-alpha",
        team_id="team-core",
        remote_addr="10.0.0.1",
    )
    request.signature = baseline.sign(request.body, request.timestamp)
    shadow = ShadowWebhookGuard(
        legacy_guard=baseline,
        candidate_guard=CandidateMismatchGuard(),
        logger=logging.getLogger("backend.tests.webhook-shadow"),
    )

    with caplog.at_level(logging.WARNING):
        result = shadow.verify(request, now=1_000)

    assert result.idempotency_key.startswith("jira:evt-1:")
    assert "webhook_guard_shadow_mismatch" in caplog.text


def test_build_persistence_adapters_forces_cutover_guard_once_production_infra_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "BACKEND_DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/devsquad",
    )
    monkeypatch.setenv("BACKEND_REDIS_URL", "redis://127.0.0.1:6379/0")

    monkeypatch.setenv("BACKEND_WEBHOOK_GUARD_MODE", "legacy")
    forced_cutover = build_persistence_adapters().webhook_guard
    assert isinstance(forced_cutover, PostgresRedisWebhookGuard)

    monkeypatch.setenv("BACKEND_WEBHOOK_GUARD_MODE", "shadow")
    shadow = build_persistence_adapters().webhook_guard
    assert isinstance(shadow, ShadowWebhookGuard)

    monkeypatch.setenv("BACKEND_WEBHOOK_GUARD_MODE", "postgres_redis")
    cutover = build_persistence_adapters().webhook_guard
    assert isinstance(cutover, PostgresRedisWebhookGuard)
