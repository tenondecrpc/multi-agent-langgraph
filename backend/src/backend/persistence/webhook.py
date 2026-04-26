from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import Engine, create_engine, insert, select, text
from sqlalchemy.exc import IntegrityError

from backend.persistence.testing.security import InMemoryWebhookGuard
from backend.security.webhook import WebhookGuardResult, WebhookRequest

from .db import tenant_guc_values
from .redis import RedisSettings, build_redis_client
from .schema import (
    webhook_idempotency_records,
    webhook_rate_limit_rejections,
    webhook_secret_rotations,
)
from .telemetry import PersistenceTelemetry, bootstrap_telemetry

WEBHOOK_GUARD_MODE_ENV_KEY = "BACKEND_WEBHOOK_GUARD_MODE"
WEBHOOK_SHARED_SECRET_ENV_KEYS = (
    "BACKEND_WEBHOOK_SHARED_SECRET",
    "BACKEND_WEBHOOK_SECRET",
)
WEBHOOK_FRESHNESS_WINDOW_ENV_KEY = "BACKEND_WEBHOOK_FRESHNESS_WINDOW_SECONDS"
WEBHOOK_PER_MINUTE_LIMIT_ENV_KEY = "BACKEND_WEBHOOK_PER_MINUTE_LIMIT"
WEBHOOK_PER_TICKET_FLOOD_LIMIT_ENV_KEY = "BACKEND_WEBHOOK_PER_TICKET_FLOOD_LIMIT"
WEBHOOK_ROTATION_OVERLAP_HOURS_ENV_KEY = "BACKEND_WEBHOOK_ROTATION_OVERLAP_HOURS"

_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
    return 1
end
redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
redis.call('EXPIRE', key, window + 10)
return 0
"""


class WebhookGuardSettings(BaseModel):
    mode: Literal["legacy", "shadow", "postgres_redis"] = "legacy"
    secret: str = "development-shared-secret"
    freshness_window_seconds: int = 300
    per_minute_limit: int = 3
    per_ticket_flood_limit: int = 20
    rotation_overlap_hours: int = 24
    ip_allowlist: list[str] = []

    @classmethod
    def from_env(cls) -> WebhookGuardSettings:
        return cls(
            mode=os.getenv(WEBHOOK_GUARD_MODE_ENV_KEY, "legacy"),
            secret=_first_env(WEBHOOK_SHARED_SECRET_ENV_KEYS, "development-shared-secret"),
            freshness_window_seconds=_int_env(WEBHOOK_FRESHNESS_WINDOW_ENV_KEY, 300),
            per_minute_limit=_int_env(WEBHOOK_PER_MINUTE_LIMIT_ENV_KEY, 3),
            per_ticket_flood_limit=_int_env(WEBHOOK_PER_TICKET_FLOOD_LIMIT_ENV_KEY, 20),
            rotation_overlap_hours=_int_env(WEBHOOK_ROTATION_OVERLAP_HOURS_ENV_KEY, 24),
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
        signature_hash: str | None = None,
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
                signature_hash=signature_hash,
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

    def get_latest_rotation(self, tenant_id: str, team_id: str) -> dict | None:
        with self._engine.begin() as connection:
            row = connection.execute(
                select(webhook_secret_rotations)
                .where(webhook_secret_rotations.c.tenant_id == tenant_id)
                .where(webhook_secret_rotations.c.team_id == team_id)
                .order_by(webhook_secret_rotations.c.created_at.desc())
                .limit(1)
            ).mappings().first()
        return dict(row) if row else None

    def record_rotation(
        self,
        tenant_id: str,
        team_id: str,
        *,
        rotation_id: str,
        previous_secret_hash: str | None,
        rotation_overlap_until: datetime | None,
        rotated_by: str,
        metadata: dict | None = None,
    ) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                webhook_secret_rotations.insert().values(
                    rotation_id=rotation_id,
                    tenant_id=tenant_id,
                    team_id=team_id,
                    previous_secret_hash=previous_secret_hash,
                    rotation_overlap_until=rotation_overlap_until,
                    rotated_by=rotated_by,
                    metadata=metadata or {},
                )
            )

    def record_rate_limit_rejection(
        self,
        tenant_id: str,
        team_id: str,
        ticket_key: str,
        source: str,
        delivery_id: str,
        remote_addr: str,
    ) -> None:
        import uuid

        with self._engine.begin() as connection:
            connection.execute(
                webhook_rate_limit_rejections.insert().values(
                    rejection_id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    team_id=team_id,
                    ticket_key=ticket_key,
                    source=source,
                    delivery_id=delivery_id,
                    remote_addr=remote_addr,
                )
            )


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

    def check_sliding_window(self, key: str, now: int, window: int, limit: int) -> bool:
        try:
            result = self._client.eval(
                _SLIDING_WINDOW_SCRIPT,
                1,
                key,
                now,
                window,
                limit,
            )
            return bool(int(result))
        except (RedisError, ValueError, TypeError):
            return False


class PostgresRedisWebhookGuard:
    def __init__(
        self,
        *,
        secret: str,
        record_store: SqlAlchemyWebhookIdempotencyStore,
        dedupe_cache: RedisWebhookDedupeCache,
        freshness_window_seconds: int = 300,
        per_minute_limit: int = 3,
        per_ticket_flood_limit: int = 20,
        rotation_overlap_hours: int = 24,
        ip_allowlist: list[str] | None = None,
        previous_secret: str | None = None,
        rotation_overlap_until: datetime | None = None,
        logger: logging.Logger | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self.secret = secret.encode("utf-8")
        self.previous_secret = previous_secret.encode("utf-8") if previous_secret else None
        self.record_store = record_store
        self.dedupe_cache = dedupe_cache
        self.freshness_window_seconds = freshness_window_seconds
        self.per_minute_limit = per_minute_limit
        self.per_ticket_flood_limit = per_ticket_flood_limit
        self.rotation_overlap_hours = rotation_overlap_hours
        self.rotation_overlap_until = rotation_overlap_until
        self.ip_allowlist = [ipaddress.ip_network(cidr) for cidr in (ip_allowlist or [])]
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
            if self.ip_allowlist:
                if not self._ip_allowed(request.remote_addr):
                    self._log_ip_rejection(request.remote_addr)
                    return WebhookGuardResult(accepted=False, rejection_reason="ip_not_allowed")

            request_signature = _normalise_signature(request.signature)
            signature_hash = hashlib.sha256(request.body.encode()).hexdigest()

            accepted, matched_previous = self._verify_signature(
                request.body, request.timestamp, request_signature,
            )
            if not accepted:
                return WebhookGuardResult(accepted=False, rejection_reason="invalid_signature")

            if matched_previous:
                self._telemetry.increment("devsquad_webhook_signature_matched_previous_total")

            if now - request.timestamp > self.freshness_window_seconds:
                return WebhookGuardResult(accepted=False, rejection_reason="stale_timestamp")

            if self._check_ticket_flood(request, now=now):
                self.record_store.record_rate_limit_rejection(
                    tenant_id=request.tenant_id,
                    team_id=request.team_id,
                    ticket_key=request.ticket_key,
                    source=request.source,
                    delivery_id=request.event_id,
                    remote_addr=request.remote_addr,
                )
                self._telemetry.increment("devsquad_webhook_rate_limit_rejections_total")
                return WebhookGuardResult(accepted=False, rejection_reason="rate_limited")

            if self._rate_limited(request, now=now):
                return WebhookGuardResult(accepted=False, rejection_reason="rate_limited")

            normalized_request = request.model_copy(update={"signature": request_signature})
            idempotency_key = _idempotency_key(normalized_request, signature_hash)
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
                signature_hash=signature_hash,
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

    def _verify_signature(
        self,
        body: str,
        timestamp: int,
        request_signature: str,
    ) -> tuple[bool, bool]:
        expected_signature = self._compute_signature(body, timestamp, self.secret)
        if hmac.compare_digest(expected_signature, request_signature):
            return True, False

        if self.previous_secret and self._is_within_overlap():
            previous_signature = self._compute_signature(body, timestamp, self.previous_secret)
            if hmac.compare_digest(previous_signature, request_signature):
                return True, True

        return False, False

    def _compute_signature(self, body: str, timestamp: int, secret: bytes) -> str:
        payload = f"{timestamp}.{body}".encode()
        return hmac.new(secret, payload, "sha256").hexdigest()

    def _is_within_overlap(self) -> bool:
        if self.rotation_overlap_until is None:
            return False
        return datetime.now(tz=UTC) <= self.rotation_overlap_until

    def _check_ticket_flood(self, request: WebhookRequest, *, now: int) -> bool:
        flood_key = f"webhook:flood:{request.tenant_id}:{request.ticket_key}"
        return self.dedupe_cache.check_sliding_window(
            flood_key,
            now=now,
            window=60,
            limit=self.per_ticket_flood_limit,
        )

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

    def _ip_allowed(self, remote_addr: str) -> bool:
        try:
            addr = ipaddress.ip_address(remote_addr)
        except ValueError:
            return False
        return any(addr in network for network in self.ip_allowlist)

    def _log_ip_rejection(self, remote_addr: str) -> None:
        self.logger.warning(
            "webhook_ip_not_allowed",
            extra={"remote_addr": remote_addr, "subsystem": "webhook_guard"},
        )

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

    record_store = SqlAlchemyWebhookIdempotencyStore(database_url, telemetry=telemetry)
    try:
        rotation = record_store.get_latest_rotation("default", "default")
    except Exception:
        rotation = None
    previous_secret = None
    rotation_overlap_until = None
    if rotation and rotation.get("rotation_overlap_until"):
        rotation_overlap_until = rotation["rotation_overlap_until"]
        if rotation_overlap_until > datetime.now(tz=UTC):
            previous_secret = rotation.get("previous_secret_hash")

    candidate_guard = PostgresRedisWebhookGuard(
        secret=resolved_settings.secret,
        record_store=record_store,
        dedupe_cache=RedisWebhookDedupeCache(redis_settings=redis_settings),
        freshness_window_seconds=resolved_settings.freshness_window_seconds,
        per_minute_limit=resolved_settings.per_minute_limit,
        per_ticket_flood_limit=resolved_settings.per_ticket_flood_limit,
        rotation_overlap_hours=resolved_settings.rotation_overlap_hours,
        ip_allowlist=resolved_settings.ip_allowlist,
        previous_secret=previous_secret,
        rotation_overlap_until=rotation_overlap_until,
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


def _idempotency_key(request: WebhookRequest, signature_hash: str | None = None) -> str:
    if signature_hash:
        return f"{request.source}:{request.event_id}:{signature_hash}"
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
