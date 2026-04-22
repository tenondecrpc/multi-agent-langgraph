from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.control_plane.shadow import ShadowComparisonReport
from backend.control_plane.store import (
    NON_TERMINAL_RUN_STATES,
    AuditEvent,
    ConfigSnapshot,
    ConfigVersionRecord,
    ControlPlaneConflictError,
    RunSnapshotBinding,
)


class InMemoryHandlerRegistry:
    def __init__(self, handler_refs: list[Any]) -> None:
        self._handlers = {
            ref.handler_name: ref.handler_kind for ref in handler_refs
        }

    def resolve(self, handler_name: str) -> str | None:
        return self._handlers.get(handler_name)


class InMemoryControlPlaneStore:
    def __init__(self) -> None:
        self.graph_versions: dict[str, ConfigVersionRecord] = {}
        self.agent_versions: dict[str, ConfigVersionRecord] = {}
        self.snapshots: dict[str, ConfigSnapshot] = {}
        self.audit_events: list[AuditEvent] = []
        self.shadow_reports: list[ShadowComparisonReport] = []
        self.run_bindings: dict[str, RunSnapshotBinding] = {}
        self._version_counts = {"graph": 0, "agent": 0}
        self._active_snapshot_id: str | None = None

    def create_graph_version(
        self,
        *,
        payload: dict[str, Any],
        actor: str,
        rationale: str,
    ) -> ConfigVersionRecord:
        return self._create_version(
            config_kind="graph",
            payload=payload,
            actor=actor,
            rationale=rationale,
        )

    def create_agent_version(
        self,
        *,
        payload: dict[str, Any],
        actor: str,
        rationale: str,
    ) -> ConfigVersionRecord:
        return self._create_version(
            config_kind="agent",
            payload=payload,
            actor=actor,
            rationale=rationale,
        )

    def activate(
        self,
        *,
        graph_version_id: str,
        agent_version_ids: dict[str, str],
        actor: str,
        rationale: str,
        comparison_report: ShadowComparisonReport,
        override_rationale: str | None = None,
        expected_active_snapshot_id: str | None = None,
    ) -> ConfigSnapshot:
        if comparison_report.blocked and override_rationale is None:
            raise ValueError(
                "Activation is blocked until the shadow comparison report is overridden."
            )
        expected_snapshot_id = expected_active_snapshot_id
        if expected_snapshot_id is None and comparison_report.active_version_id != "none":
            expected_snapshot_id = comparison_report.active_version_id
        if expected_snapshot_id != self._active_snapshot_id:
            raise ControlPlaneConflictError(
                "The active snapshot changed before activation could commit."
            )

        self._require_graph_version(graph_version_id)
        for agent_version_id in agent_version_ids.values():
            self._require_agent_version(agent_version_id)

        self.shadow_reports.append(comparison_report)
        snapshot = ConfigSnapshot(
            snapshot_id=str(uuid4()),
            graph_version_id=graph_version_id,
            agent_version_ids=agent_version_ids,
            created_at=datetime.now(tz=UTC),
            created_by=actor,
            evidence_summary="; ".join(comparison_report.blocking_reasons)
            if comparison_report.blocked
            else "shadow-evidence-passed",
        )
        self.snapshots[snapshot.snapshot_id] = snapshot
        self._active_snapshot_id = snapshot.snapshot_id
        self.audit_events.append(
            AuditEvent(
                event_id=str(uuid4()),
                action="activate",
                actor=actor,
                rationale=override_rationale or rationale,
                target_id=snapshot.snapshot_id,
                evidence_summary=snapshot.evidence_summary,
            )
        )
        return snapshot

    def rollback(
        self,
        *,
        snapshot_id: str,
        actor: str,
        rationale: str,
        expected_active_snapshot_id: str | None = None,
    ) -> ConfigSnapshot:
        if (
            expected_active_snapshot_id is not None
            and expected_active_snapshot_id != self._active_snapshot_id
        ):
            raise ControlPlaneConflictError(
                "The active snapshot changed before rollback could commit."
            )
        snapshot = self.snapshots[snapshot_id]
        self._active_snapshot_id = snapshot_id
        self.audit_events.append(
            AuditEvent(
                event_id=str(uuid4()),
                action="rollback",
                actor=actor,
                rationale=rationale,
                target_id=snapshot_id,
                evidence_summary="rollback-reactivated-snapshot",
            )
        )
        return snapshot

    def active_snapshot(self) -> ConfigSnapshot:
        if self._active_snapshot_id is None:
            raise KeyError("No active snapshot is available.")
        return self.snapshots[self._active_snapshot_id]

    def pin_run_snapshot(self, run_id: str, snapshot_id: str, status: str) -> None:
        self.run_bindings[run_id] = RunSnapshotBinding(
            run_id=run_id,
            snapshot_id=snapshot_id,
            status=status,
        )

    def snapshot_for_run(self, run_id: str) -> ConfigSnapshot:
        binding = self.run_bindings[run_id]
        return self.snapshots[binding.snapshot_id]

    def update_run_status(self, run_id: str, status: str) -> None:
        binding = self.run_bindings[run_id]
        self.run_bindings[run_id] = binding.model_copy(update={"status": status})

    def cleanup_retired_snapshots(self) -> list[str]:
        referenced_snapshot_ids = {
            binding.snapshot_id
            for binding in self.run_bindings.values()
            if binding.status in NON_TERMINAL_RUN_STATES
        }
        deleted: list[str] = []
        for snapshot_id in list(self.snapshots):
            if snapshot_id == self._active_snapshot_id:
                continue
            if snapshot_id in referenced_snapshot_ids:
                continue
            deleted.append(snapshot_id)
            del self.snapshots[snapshot_id]
        return deleted

    def _create_version(
        self,
        *,
        config_kind: str,
        payload: dict[str, Any],
        actor: str,
        rationale: str,
    ) -> ConfigVersionRecord:
        self._version_counts[config_kind] += 1
        record = ConfigVersionRecord(
            record_id=str(uuid4()),
            config_kind=config_kind,
            version_number=self._version_counts[config_kind],
            created_by=actor,
            rationale=rationale,
            created_at=datetime.now(tz=UTC),
            payload=payload,
        )
        target = self.graph_versions if config_kind == "graph" else self.agent_versions
        target[record.record_id] = record
        self.audit_events.append(
            AuditEvent(
                event_id=str(uuid4()),
                action="create_graph" if config_kind == "graph" else "create_agent",
                actor=actor,
                rationale=rationale,
                target_id=record.record_id,
            )
        )
        return record

    def _require_graph_version(self, graph_version_id: str) -> None:
        if graph_version_id not in self.graph_versions:
            raise KeyError(f"Unknown graph version `{graph_version_id}`.")

    def _require_agent_version(self, agent_version_id: str) -> None:
        if agent_version_id not in self.agent_versions:
            raise KeyError(f"Unknown agent version `{agent_version_id}`.")
