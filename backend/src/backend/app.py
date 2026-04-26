from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from .api_deprecations import ApiDeprecation
from .api_versioning import ApiVersioningConfig, install_api_versioning
from .billing import build_billing_router
from .knowledge import (
    InternalRagSettings,
    KnowledgeRepository,
    build_knowledge_router,
    probe_pgvector_extension,
)
from .operations.status_page import PublicStatusPage, PublicStatusPageService
from .persistence.factory import PersistenceAdapters, build_persistence_adapters
from .persistence.migrations import MigrationRunner
from .platform import build_platform_routers
from .runtime import ExecutionRequest, PlanningRequest, RuntimeWorkflow, TicketRunState


class RuntimeSimulationRequest(BaseModel):
    planning: PlanningRequest
    execution: ExecutionRequest = Field(default_factory=ExecutionRequest)
    escalation_sinks: dict[str, str] | None = None


def create_app(
    workflow: RuntimeWorkflow | None = None,
    persistence: PersistenceAdapters | None = None,
    migration_runner: MigrationRunner | None = None,
    internal_rag_settings: InternalRagSettings | None = None,
    knowledge_repository: KnowledgeRepository | None = None,
    api_deprecations: tuple[ApiDeprecation, ...] = (),
) -> FastAPI:
    adapters = persistence or build_persistence_adapters()
    runner = migration_runner or MigrationRunner()
    rag_settings = internal_rag_settings or InternalRagSettings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        status = runner.ensure_current()
        app.state.persistence_migration_status = status
        adapters.health.update_migration_status(status)
        adapters.telemetry.set_gauge(
            "devsquad_persistence_migration_info",
            1.0,
            revision=status.current_revision or "none",
        )
        try:
            snapshot = adapters.control_plane_store.active_snapshot()
            adapters.health.update_active_snapshot_id(snapshot.snapshot_id)
        except Exception:
            adapters.health.update_active_snapshot_id(None)
        rag_probe = await probe_pgvector_extension(rag_settings)
        adapters.health.update_capability_probe(
            "internal_rag",
            ready=rag_probe.ready,
            reason=rag_probe.reason,
        )
        yield

    app = FastAPI(title="LangGraph Dev Squad Backend", version="0.1.0", lifespan=lifespan)
    app.state.persistence = adapters
    install_api_versioning(
        app,
        ApiVersioningConfig(
            deprecations=api_deprecations,
            telemetry=adapters.telemetry,
        ),
    )
    runtime_workflow = workflow or RuntimeWorkflow(repository=adapters.run_repository)

    system_router = APIRouter(tags=["system"])
    runtime_router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])
    status_router = APIRouter(prefix="/api/v1", tags=["status"])

    @system_router.get("/healthz")
    def healthz(response: Response) -> dict[str, object]:
        probe = adapters.health.liveness()
        response.status_code = 200 if probe.status == "ok" else 503
        return {
            "status": probe.status,
            "reasons": probe.reasons,
            "persistence": adapters.health.snapshot().model_dump(mode="json"),
        }

    @system_router.get("/readyz")
    def readyz(response: Response) -> dict[str, object]:
        probe = adapters.health.readiness()
        response.status_code = 200 if probe.status == "ok" else 503
        return {
            "status": probe.status,
            "reasons": probe.reasons,
            "persistence": adapters.health.snapshot().model_dump(mode="json"),
        }

    @system_router.get("/metrics")
    def metrics() -> Response:
        return Response(
            content=adapters.telemetry.render_prometheus(),
            media_type="text/plain; version=0.0.4",
        )

    @runtime_router.post("/simulate", response_model=TicketRunState)
    def simulate_run(request: RuntimeSimulationRequest) -> TicketRunState:
        try:
            return runtime_workflow.execute(
                planning_request=request.planning,
                execution_request=request.execution,
                escalation_sinks=request.escalation_sinks,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @status_router.get("/status-page", response_model=PublicStatusPage)
    def status_page() -> PublicStatusPage:
        return PublicStatusPageService(
            health=adapters.health,
            telemetry=adapters.telemetry,
        ).snapshot()

    app.include_router(system_router)
    app.include_router(runtime_router)
    app.include_router(status_router)
    for router in build_platform_routers(
        worker_controller=adapters.worker_controller,
        webhook_guard=adapters.webhook_guard,
        api_deprecations=api_deprecations,
        metering_ledger=adapters.metering_ledger,
    ):
        app.include_router(router)
    app.include_router(
        build_knowledge_router(
            repository=knowledge_repository,
            settings=rag_settings,
            telemetry=adapters.telemetry,
        )
    )
    from .supply_chain.admission import build_admission_router

    app.include_router(build_admission_router())
    app.include_router(
        build_billing_router(
            metering_ledger=adapters.metering_ledger,
        )
    )
    return app


app = create_app()


def main() -> None:
    print("Use `uv run --project backend fastapi dev backend/src/backend/app.py` to start the API.")
