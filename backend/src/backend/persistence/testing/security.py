from __future__ import annotations

import hashlib
import hmac
import ipaddress

from backend.security.webhook import WebhookGuardResult, WebhookRequest


class InMemoryWebhookGuard:
    def __init__(
        self,
        *,
        secret: str,
        freshness_window_seconds: int = 300,
        per_minute_limit: int = 3,
        per_ticket_flood_limit: int = 20,
        ip_allowlist: list[str] | None = None,
    ) -> None:
        self.secret = secret.encode("utf-8")
        self.freshness_window_seconds = freshness_window_seconds
        self.per_minute_limit = per_minute_limit
        self.per_ticket_flood_limit = per_ticket_flood_limit
        self.ip_allowlist = [ipaddress.ip_network(cidr) for cidr in (ip_allowlist or [])]
        self._seen_events: set[str] = set()
        self._request_windows: dict[tuple[str, str], list[int]] = {}
        self._ticket_windows: dict[str, list[int]] = {}

    def verify(self, request: WebhookRequest, *, now: int) -> WebhookGuardResult:
        if self.ip_allowlist:
            if not self._ip_allowed(request.remote_addr):
                return WebhookGuardResult(accepted=False, rejection_reason="ip_not_allowed")

        expected_signature = self.sign(request.body, request.timestamp)
        if not hmac.compare_digest(expected_signature, request.signature):
            return WebhookGuardResult(accepted=False, rejection_reason="invalid_signature")

        if now - request.timestamp > self.freshness_window_seconds:
            return WebhookGuardResult(accepted=False, rejection_reason="stale_timestamp")

        signature_hash = hashlib.sha256(request.body.encode()).hexdigest()
        idempotency_key = f"{request.source}:{request.event_id}:{signature_hash}"
        if idempotency_key in self._seen_events:
            return WebhookGuardResult(
                accepted=True,
                deduplicated=True,
                idempotency_key=idempotency_key,
            )

        ticket_key = getattr(request, "ticket_key", None) or "unknown"
        if self._ticket_flood_exceeded(ticket_key, now=now):
            return WebhookGuardResult(accepted=False, rejection_reason="rate_limited")

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

    def _ip_allowed(self, remote_addr: str) -> bool:
        try:
            addr = ipaddress.ip_address(remote_addr)
        except ValueError:
            return False
        return any(addr in network for network in self.ip_allowlist)

    def _ticket_flood_exceeded(self, ticket_key: str, *, now: int) -> bool:
        times = [t for t in self._ticket_windows.get(ticket_key, []) if now - t < 60]
        if len(times) >= self.per_ticket_flood_limit:
            self._ticket_windows[ticket_key] = times
            return True
        times.append(now)
        self._ticket_windows[ticket_key] = times
        return False
