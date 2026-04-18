from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .queue import InMemoryWorkerController
from .sandbox import SandboxTemplateBuilder


class JiraWebhookEvent(BaseModel):
    event_id: str
    ticket_key: str
    tenant_id: str
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
    worker_controller: InMemoryWorkerController | None = None,
    sandbox_builder: SandboxTemplateBuilder | None = None,
) -> list[APIRouter]:
    controller = worker_controller or InMemoryWorkerController()
    builder = sandbox_builder or SandboxTemplateBuilder()

    webhooks_router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
    runs_router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
    streams_router = APIRouter(prefix="/api/v1/streams", tags=["streams"])
    auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
    admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
    metering_router = APIRouter(prefix="/api/v1/metering", tags=["metering"])

    @webhooks_router.post("/jira")
    def receive_jira_webhook(event: JiraWebhookEvent) -> dict[str, str | bool]:
        return {
            "event_id": event.event_id,
            "ticket_key": event.ticket_key,
            "accepted": True,
            "deduplicated": False,
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
