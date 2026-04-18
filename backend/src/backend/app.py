from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .platform import build_platform_routers
from .runtime import ExecutionRequest, PlanningRequest, RuntimeWorkflow, TicketRunState


class RuntimeSimulationRequest(BaseModel):
    planning: PlanningRequest
    execution: ExecutionRequest = Field(default_factory=ExecutionRequest)
    escalation_sinks: dict[str, str] | None = None


def create_app(workflow: RuntimeWorkflow | None = None) -> FastAPI:
    app = FastAPI(title="LangGraph Dev Squad Backend", version="0.1.0")
    runtime_workflow = workflow or RuntimeWorkflow()

    system_router = APIRouter(tags=["system"])
    runtime_router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])

    @system_router.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @system_router.get("/readyz")
    def readyz() -> dict[str, str]:
        return {"status": "ready"}

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

    app.include_router(system_router)
    app.include_router(runtime_router)
    for router in build_platform_routers():
        app.include_router(router)
    return app


app = create_app()


def main() -> None:
    print("Use `uv run --project backend fastapi dev backend/src/backend/app.py` to start the API.")
