from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class WorkerPoolProfile(BaseModel):
    name: Literal["primary", "shadow"]
    queue_name: str
    read_only: bool


class SandboxJobTemplate(BaseModel):
    name: str
    namespace: str
    runtime_class_name: str
    run_as_non_root: bool
    read_only_root_filesystem: bool
    cpu_limit: str
    memory_limit: str
    egress_allowlist: list[str]
    labels: dict[str, str]
    cleanup_after_seconds: int
    service_account: str
    worker_pool: WorkerPoolProfile


class SandboxTemplateBuilder:
    def __init__(self, *, cleanup_after_seconds: int = 900) -> None:
        self.cleanup_after_seconds = cleanup_after_seconds

    def build(
        self,
        *,
        tenant_id: str,
        team_id: str,
        run_id: str,
        worker_pool: Literal["primary", "shadow"] = "primary",
    ) -> SandboxJobTemplate:
        profile = WorkerPoolProfile(
            name=worker_pool,
            queue_name="ticket-runs" if worker_pool == "primary" else "shadow-ticket-runs",
            read_only=worker_pool == "shadow",
        )
        return SandboxJobTemplate(
            name=f"{worker_pool}-sandbox-{run_id}",
            namespace=f"tenant-{tenant_id}",
            runtime_class_name="runsc",
            run_as_non_root=True,
            read_only_root_filesystem=profile.read_only,
            cpu_limit="2",
            memory_limit="2Gi",
            egress_allowlist=["github.internal", "jira.internal"],
            labels={
                "tenant_id": tenant_id,
                "team_id": team_id,
                "run_id": run_id,
                "cleanup": "true",
                "worker_pool": worker_pool,
            },
            cleanup_after_seconds=self.cleanup_after_seconds,
            service_account=f"{worker_pool}-sandbox-sa",
            worker_pool=profile,
        )
