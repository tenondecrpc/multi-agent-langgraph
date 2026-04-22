from __future__ import annotations

import hashlib
import hmac

from backend.security.webhook import WebhookGuardResult, WebhookRequest


class InMemoryWebhookGuard:
    def __init__(
        self,
        *,
        secret: str,
        freshness_window_seconds: int = 300,
        per_minute_limit: int = 3,
    ) -> None:
        self.secret = secret.encode("utf-8")
        self.freshness_window_seconds = freshness_window_seconds
        self.per_minute_limit = per_minute_limit
        self._seen_events: set[str] = set()
        self._request_windows: dict[tuple[str, str], list[int]] = {}

    def verify(self, request: WebhookRequest, *, now: int) -> WebhookGuardResult:
        expected_signature = self.sign(request.body, request.timestamp)
        if not hmac.compare_digest(expected_signature, request.signature):
            return WebhookGuardResult(accepted=False, rejection_reason="invalid_signature")

        if now - request.timestamp > self.freshness_window_seconds:
            return WebhookGuardResult(accepted=False, rejection_reason="stale_timestamp")

        idempotency_key = f"{request.endpoint}:{request.event_id}"
        if idempotency_key in self._seen_events:
            return WebhookGuardResult(
                accepted=True,
                deduplicated=True,
                idempotency_key=idempotency_key,
            )

        bucket_key = (request.endpoint, request.remote_addr)
        request_times = [
            timestamp for timestamp in self._request_windows.get(bucket_key, []) if now - timestamp < 60
        ]
        if len(request_times) >= self.per_minute_limit:
            self._request_windows[bucket_key] = request_times
            return WebhookGuardResult(accepted=False, rejection_reason="rate_limited")

        request_times.append(now)
        self._request_windows[bucket_key] = request_times
        self._seen_events.add(idempotency_key)
        return WebhookGuardResult(accepted=True, idempotency_key=idempotency_key)

    def sign(self, body: str, timestamp: int) -> str:
        payload = f"{timestamp}.{body}".encode()
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()
