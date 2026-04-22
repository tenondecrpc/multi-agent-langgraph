from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from time import time
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.persistence.contracts import WebhookGuard, WorkerController
from backend.persistence.factory import build_persistence_adapters
from backend.security.webhook import WebhookRequest

from .sandbox import SandboxTemplateBuilder

logger = logging.getLogger(__name__)


class JiraWebhookEvent(BaseModel):
    event_id: str
    ticket_key: str
    tenant_id: str
    team_id: str
    summary: str


def route_inventory() -> list[dict[str, str]]:
    return [
        {"path": "/api/v1/webhooks/jira", "method": "POST", "category": "webhooks"},
        {"path": "/api/v1/runs/{run_id}", "method": "GET", "category": "runs"},
        {"path": "/api/v1/streams/runs", "method": "GET", "category": "streams"},
        {"path": "/api/v1/auth/callback", "method": "GET", "category": "auth"},
        {"path": "/api/v1/admin/profile", "method": "GET", "category": "admin"},
        {"path": "/api/v1/metering/exports", "method": "GET", "category": "metering"},
    ]


def _event_stream() -> Iterator[str]:
    yield "event: ping\ndata: {\"status\":\"ok\"}\n\n"


def build_platform_routers(
    *,
    worker_controller: WorkerController | None = None,
    webhook_guard: WebhookGuard | None = None,
    sandbox_builder: SandboxTemplateBuilder | None = None,
    now_provider: Callable[[], int] | None = None,
) -> list[APIRouter]:
    adapters = None
    if worker_controller is None or webhook_guard is None:
        adapters = build_persistence_adapters()
    if adapters is None:
        adapters = build_persistence_adapters()
    controller = worker_controller or adapters.worker_controller
    guard = webhook_guard or adapters.webhook_guard
    builder = sandbox_builder or SandboxTemplateBuilder()
    resolve_now = now_provider or _epoch_seconds

    webhooks_router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
    runs_router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
    streams_router = APIRouter(prefix="/api/v1/streams", tags=["streams"])
    auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
    admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
    metering_router = APIRouter(prefix="/api/v1/metering", tags=["metering"])

    @webhooks_router.post("/jira")
    async def receive_jira_webhook(
        event: JiraWebhookEvent,
        request: Request,
        response: Response,
        x_hub_signature_256: Annotated[str, Header(alias="X-Hub-Signature-256")],
        x_atlassian_webhook_timestamp: Annotated[int, Header(alias="X-Atlassian-Webhook-Timestamp")],
    ) -> dict[str, str | bool]:
        raw_body = (await request.body()).decode("utf-8")
        verification = guard.verify(
            WebhookRequest(
                body=raw_body,
                signature=_normalise_signature(x_hub_signature_256),
                timestamp=x_atlassian_webhook_timestamp,
                event_id=event.event_id,
                tenant_id=event.tenant_id,
                team_id=event.team_id,
                remote_addr=request.client.host if request.client else "unknown",
            ),
            now=resolve_now(),
        )
        if not verification.accepted:
            logger.warning(
                "webhook_request_rejected",
                extra={
                    "delivery_id": event.event_id,
                    "tenant_id": event.tenant_id,
                    "team_id": event.team_id,
                    "reason": verification.rejection_reason,
                },
            )
            raise HTTPException(
                status_code=_rejection_status_code(verification.rejection_reason),
                detail=verification.rejection_reason or "webhook_rejected",
            )

        if verification.deduplicated:
            response.headers["X-Webhook-Deduplicated"] = "true"

        return {
            "event_id": event.event_id,
            "ticket_key": event.ticket_key,
            "accepted": verification.accepted,
            "deduplicated": verification.deduplicated,
        }

    @runs_router.get("/{run_id}")
    def get_run(run_id: str) -> dict[str, str]:
        return {"run_id": run_id, "status": "planned"}

    @streams_router.get("/runs")
    def stream_runs() -> StreamingResponse:
        return StreamingResponse(_event_stream(), media_type="text/event-stream")

    @auth_router.get("/callback")
    def auth_callback(code: str | None = None) -> dict[str, str]:
        return {"status": "accepted", "code": code or ""}

    @admin_router.get("/profile")
    def admin_profile() -> dict[str, object]:
        return {
            "route_inventory": route_inventory(),
            "draining_workers": sorted(controller.draining_workers),
            "persistence_status": adapters.health.snapshot().model_dump(mode="json"),
            "primary_sandbox": builder.build(
                tenant_id="tenant-alpha",
                team_id="team-core",
                run_id="sample-run",
                worker_pool="primary",
            ).model_dump(),
            "shadow_sandbox": builder.build(
                tenant_id="tenant-alpha",
                team_id="team-core",
                run_id="sample-run",
                worker_pool="shadow",
            ).model_dump(),
        }

    @metering_router.get("/exports")
    def list_metering_exports() -> dict[str, list[dict[str, str]]]:
        return {"exports": []}

    return [
        webhooks_router,
        runs_router,
        streams_router,
        auth_router,
        admin_router,
        metering_router,
    ]


def _epoch_seconds() -> int:
    return int(time())


def _normalise_signature(signature: str) -> str:
    if signature.startswith("sha256="):
        return signature.removeprefix("sha256=")
    return signature


def _rejection_status_code(reason: str | None) -> int:
    if reason in {"invalid_signature", "stale_timestamp"}:
        return status.HTTP_401_UNAUTHORIZED
    if reason == "rate_limited":
        return status.HTTP_429_TOO_MANY_REQUESTS
    return status.HTTP_400_BAD_REQUEST
