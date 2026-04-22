from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.persistence.testing.control_plane import InMemoryControlPlaneStore

RunState = Literal["active", "paused", "shadow", "dlq", "completed", "failed"]
NON_TERMINAL_RUN_STATES = {"active", "paused", "shadow", "dlq"}


class ControlPlaneConflictError(RuntimeError):
    """Raised when activation or rollback loses an optimistic-concurrency race."""


class ConfigVersionRecord(BaseModel):
    record_id: str
    config_kind: Literal["graph", "agent"]
    version_number: int
    created_by: str
    rationale: str
    created_at: datetime
    payload: dict[str, Any]


class ConfigSnapshot(BaseModel):
    snapshot_id: str
    graph_version_id: str
    agent_version_ids: dict[str, str]
    created_at: datetime
    created_by: str
    evidence_summary: str


class RunSnapshotBinding(BaseModel):
    run_id: str
    snapshot_id: str
    status: RunState


class AuditEvent(BaseModel):
    event_id: str
    action: Literal["create_graph", "create_agent", "activate", "rollback"]
    actor: str
    rationale: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    target_id: str
    evidence_summary: str | None = None


__all__ = [
    "AuditEvent",
    "ConfigSnapshot",
    "ConfigVersionRecord",
    "ControlPlaneConflictError",
    "InMemoryControlPlaneStore",
    "NON_TERMINAL_RUN_STATES",
    "RunSnapshotBinding",
    "RunState",
]


def __getattr__(name: str):
    if name == "InMemoryControlPlaneStore":
        from backend.persistence.testing.control_plane import InMemoryControlPlaneStore

        return InMemoryControlPlaneStore
    raise AttributeError(name)
