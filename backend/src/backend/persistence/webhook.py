from __future__ import annotations

import hmac
import logging
import os
from typing import Literal

from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import Engine, create_engine, insert, text
from sqlalchemy.exc import IntegrityError

from backend.persistence.testing.security import InMemoryWebhookGuard
from backend.security.webhook import WebhookGuardResult, WebhookRequest

from .db import tenant_guc_values
from .redis import RedisSettings, build_redis_client
from .schema import webhook_idempotency_records
from .telemetry import PersistenceTelemetry, bootstrap_telemetry

WEBHOOK_GUARD_MODE_ENV_KEY = "BACKEND_WEBHOOK_GUARD_MODE"
WEBHOOK_SHARED_SECRET_ENV_KEYS = (
    "BACKEND_WEBHOOK_SHARED_SECRET",
    "BACKEND_WEBHOOK_SECRET",
)
WEBHOOK_FRESHNESS_WINDOW_ENV_KEY = "BACKEND_WEBHOOK_FRESHNESS_WINDOW_SECONDS"
WEBHOOK_PER_MINUTE_LIMIT_ENV_KEY = "BACKEND_WEBHOOK_PER_MINUTE_LIMIT"


class WebhookGuardSettings(BaseModel):
    mode: Literal["legacy", "shadow", "postgres_redis"] = "legacy"
    secret: str = "development-shared-secret"
    freshness_window_seconds: int = 300
    per_minute_limit: int = 3

    @classmethod
    def from_env(cls) -> WebhookGuardSettings:
        return cls(
            mode=os.getenv(WEBHOOK_GUARD_MODE_ENV_KEY, "legacy"),
            secret=_first_env(WEBHOOK_SHARED_SECRET_ENV_KEYS, "development-shared-secret"),
            freshness_window_seconds=_int_env(WEBHOOK_FRESHNESS_WINDOW_ENV_KEY, 300),
            per_minute_limit=_int_env(WEBHOOK_PER_MINUTE_LIMIT_ENV_KEY, 3),
        )


class SqlAlchemyWebhookIdempotencyStore:
    def __init__(
        self,
        database_url: str,
        *,
        engine: Engine | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self._engine = engine or create_engine(database_url, future=True, pool_pre_ping=True)
        self._telemetry = telemetry or bootstrap_telemetry()

    def insert_delivery(
        self,
        request: WebhookRequest,
        *,
        disposition_status: str,
    ) -> bool:
        with self._telemetry.trace(
            "webhook_idempotency_insert_delivery",
            subsystem="webhook_guard",
            operation="insert_delivery",
            tenant_id=request.tenant_id,
            team_id=request.team_id,
        ):
            statement = insert(webhook_idempotency_records).values(
                source=request.source,
                delivery_id=request.event_id,
                tenant_id=request.tenant_id,
                team_id=request.team_id,
                endpoint=request.endpoint,
                hmac_digest=request.signature,
                disposition_status=disposition_status,
            )

            try:
                with self._engine.begin() as connection:
                    for key, value in tenant_guc_values(
                        tenant_id=request.tenant_id,
                        team_id=request.team_id,
                    ).items():
                        connection.execute(
                            text("SELECT set_config(:key, :value, true)"),
                            {"key": key, "value": value},
                        )
                    connection.execute(statement)
            except IntegrityError as exc:
                if _is_duplicate_delivery(exc):
                    return False
                raise

            return True


class RedisWebhookDedupeCache:
    def __init__(
        self,
        *,
        redis_settings: RedisSettings | None = None,
        client: Redis | None = None,
    ) -> None:
        if client is None and redis_settings is None:
            raise ValueError("redis_settings or client is required")

        self._client = client or build_redis_client(redis_settings or RedisSettings())

    def seen(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def remember(self, key: str, *, ttl_seconds: int) -> None:
        self._client.set(key, "1", ex=ttl_seconds)


class PostgresRedisWebhookGuard:
    def __init__(
        self,
        *,
        secret: str,
        record_store: SqlAlchemyWebhookIdempotencyStore,
        dedupe_cache: RedisWebhookDedupeCache,
        freshness_window_seconds: int = 300,
        per_minute_limit: int = 3,
        logger: logging.Logger | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self.secret = secret.encode("utf-8")
        self.record_store = record_store
        self.dedupe_cache = dedupe_cache
        self.freshness_window_seconds = freshness_window_seconds
        self.per_minute_limit = per_minute_limit
        self.logger = logger or logging.getLogger(__name__)
        self._telemetry = telemetry or bootstrap_telemetry()
        self._request_windows: dict[tuple[str, str], list[int]] = {}

    def verify(self, request: WebhookRequest, *, now: int) -> WebhookGuardResult:
        with self._telemetry.trace(
            "webhook_guard_verify",
            subsystem="webhook_guard",
            operation="verify",
            tenant_id=request.tenant_id,
            team_id=request.team_id,
        ):
            request_signature = _normalise_signature(request.signature)
            expected_signature = self.sign(request.body, request.timestamp)
            if not hmac.compare_digest(expected_signature, request_signature):
                return WebhookGuardResult(accepted=False, rejection_reason="invalid_signature")

            if now - request.timestamp > self.freshness_window_seconds:
                return WebhookGuardResult(accepted=False, rejection_reason="stale_timestamp")

            if self._rate_limited(request, now=now):
                return WebhookGuardResult(accepted=False, rejection_reason="rate_limited")

            normalized_request = request.model_copy(update={"signature": request_signature})
            idempotency_key = _idempotency_key(normalized_request)
            if self._cache_seen(idempotency_key):
                self._telemetry.increment("devsquad_webhook_dedupe_hits_total")
                return WebhookGuardResult(
                    accepted=True,
                    deduplicated=True,
                    idempotency_key=idempotency_key,
                )

            inserted = self.record_store.insert_delivery(
                normalized_request,
                disposition_status="accepted",
            )
            if not inserted:
                self._telemetry.increment("devsquad_webhook_dedupe_hits_total")
                self._remember_best_effort(idempotency_key)
                return WebhookGuardResult(
                    accepted=True,
                    deduplicated=True,
                    idempotency_key=idempotency_key,
                )

            self._remember_best_effort(idempotency_key)
            return WebhookGuardResult(accepted=True, idempotency_key=idempotency_key)

    def sign(self, body: str, timestamp: int) -> str:
        with self._telemetry.trace(
            "webhook_guard_sign",
            subsystem="webhook_guard",
            operation="sign",
        ):
            payload = f"{timestamp}.{body}".encode()
            return hmac.new(self.secret, payload, "sha256").hexdigest()

    def _rate_limited(self, request: WebhookRequest, *, now: int) -> bool:
        bucket_key = (request.endpoint, request.remote_addr)
        request_times = [
            timestamp
            for timestamp in self._request_windows.get(bucket_key, [])
            if now - timestamp < 60
        ]
        if len(request_times) >= self.per_minute_limit:
            self._request_windows[bucket_key] = request_times
            return True

        request_times.append(now)
        self._request_windows[bucket_key] = request_times
        return False

    def _cache_seen(self, idempotency_key: str) -> bool:
        try:
            return self.dedupe_cache.seen(idempotency_key)
        except RedisError:
            self.logger.warning(
                "webhook_guard_cache_read_failed",
                extra={"idempotency_key": idempotency_key},
            )
            return False

    def _remember_best_effort(self, idempotency_key: str) -> None:
        try:
            self.dedupe_cache.remember(
                idempotency_key,
                ttl_seconds=self.freshness_window_seconds,
            )
        except RedisError:
            self.logger.warning(
                "webhook_guard_cache_write_failed",
                extra={"idempotency_key": idempotency_key},
            )


class ShadowWebhookGuard:
    def __init__(
        self,
        *,
        legacy_guard: InMemoryWebhookGuard,
        candidate_guard: PostgresRedisWebhookGuard,
        logger: logging.Logger | None = None,
    ) -> None:
        self.legacy_guard = legacy_guard
        self.candidate_guard = candidate_guard
        self.logger = logger or logging.getLogger(__name__)

    def verify(self, request: WebhookRequest, *, now: int) -> WebhookGuardResult:
        legacy_result = self.legacy_guard.verify(request, now=now)
        try:
            candidate_result = self.candidate_guard.verify(request, now=now)
        except Exception as exc:  # pragma: no cover - defensive path
            self.logger.warning(
                "webhook_guard_shadow_candidate_failed",
                extra={
                    "delivery_id": request.event_id,
                    "source": request.source,
                    "error": str(exc),
                },
            )
            return legacy_result

        if candidate_result != legacy_result:
            self.logger.warning(
                "webhook_guard_shadow_mismatch",
                extra={
                    "delivery_id": request.event_id,
                    "source": request.source,
                    "legacy_result": legacy_result.model_dump(mode="json"),
                    "candidate_result": candidate_result.model_dump(mode="json"),
                },
            )
        return legacy_result

    def sign(self, body: str, timestamp: int) -> str:
        return self.legacy_guard.sign(body, timestamp)


def build_webhook_guard(
    *,
    legacy_guard: InMemoryWebhookGuard | None,
    database_url: str | None,
    redis_settings: RedisSettings,
    settings: WebhookGuardSettings | None = None,
    logger: logging.Logger | None = None,
    telemetry: PersistenceTelemetry | None = None,
) -> InMemoryWebhookGuard | ShadowWebhookGuard | PostgresRedisWebhookGuard:
    resolved_settings = settings or WebhookGuardSettings.from_env()
    resolved_logger = logger or logging.getLogger(__name__)

    if resolved_settings.mode == "legacy":
        if legacy_guard is None:
            raise RuntimeError("Legacy webhook mode requires an in-memory test double.")
        return legacy_guard

    if not database_url:
        raise RuntimeError("BACKEND_WEBHOOK_GUARD_MODE requires a configured PostgreSQL database URL")
    if not redis_settings.configured:
        raise RuntimeError("BACKEND_WEBHOOK_GUARD_MODE requires a configured Redis URL")

    candidate_guard = PostgresRedisWebhookGuard(
        secret=resolved_settings.secret,
        record_store=SqlAlchemyWebhookIdempotencyStore(database_url, telemetry=telemetry),
        dedupe_cache=RedisWebhookDedupeCache(redis_settings=redis_settings),
        freshness_window_seconds=resolved_settings.freshness_window_seconds,
        per_minute_limit=resolved_settings.per_minute_limit,
        logger=resolved_logger,
        telemetry=telemetry,
    )

    if resolved_settings.mode == "shadow":
        if legacy_guard is None:
            raise RuntimeError("Shadow webhook mode requires an in-memory baseline guard.")
        return ShadowWebhookGuard(
            legacy_guard=legacy_guard,
            candidate_guard=candidate_guard,
            logger=resolved_logger,
        )

    return candidate_guard


def _idempotency_key(request: WebhookRequest) -> str:
    return f"{request.source}:{request.event_id}"


def _is_duplicate_delivery(error: IntegrityError) -> bool:
    sqlstate = getattr(getattr(error, "orig", None), "sqlstate", None)
    if sqlstate == "23505":
        return True
    return "uq_webhook_idempotency_source_delivery" in str(error.orig)


def _normalise_signature(signature: str) -> str:
    if signature.startswith("sha256="):
        return signature.removeprefix("sha256=")
    return signature


def _first_env(keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


def _int_env(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    return int(value)
