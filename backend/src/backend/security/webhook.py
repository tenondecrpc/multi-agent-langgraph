from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.persistence.testing.security import InMemoryWebhookGuard


class WebhookRequest(BaseModel):
    body: str
    signature: str
    timestamp: int
    event_id: str
    tenant_id: str
    team_id: str
    remote_addr: str
    source: str = "jira"
    endpoint: str = "/api/v1/webhooks/jira"


class WebhookGuardResult(BaseModel):
    accepted: bool
    deduplicated: bool = False
    rejection_reason: str | None = None
    idempotency_key: str | None = None


__all__ = [
    "InMemoryWebhookGuard",
    "WebhookGuardResult",
    "WebhookRequest",
]


def __getattr__(name: str):
    if name == "InMemoryWebhookGuard":
        from backend.persistence.testing.security import InMemoryWebhookGuard

        return InMemoryWebhookGuard
    raise AttributeError(name)
