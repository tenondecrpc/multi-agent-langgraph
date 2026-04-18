from __future__ import annotations

from hashlib import sha256
from typing import Protocol

from .models import (
    ArtifactKind,
    ContextRequest,
    ContextSource,
    PlanningRequest,
    QualityTarget,
    ResolvedContextBundle,
    RuntimeArtifact,
    TaskItem,
    TaskListArtifact,
    TestTarget,
    TicketRunState,
)


class RuntimeConstitutionLoader(Protocol):
    def load_for_run(
        self, tenant_id: str, repo_id: str, config_snapshot_id: str
    ) -> RuntimeArtifact: ...


class PlannerArtifactService(Protocol):
    def create_feature_spec(
        self, run: TicketRunState, planning_request: PlanningRequest, context: ResolvedContextBundle
    ) -> RuntimeArtifact: ...

    def create_clarification_notes(
        self, run: TicketRunState, planning_request: PlanningRequest
    ) -> RuntimeArtifact: ...

    def create_implementation_plan(
        self, run: TicketRunState, planning_request: PlanningRequest
    ) -> RuntimeArtifact: ...

    def create_task_list(
        self, run: TicketRunState, planning_request: PlanningRequest
    ) -> tuple[TaskListArtifact | None, bool, list[str]]: ...


class StaticConstitutionLoader:
    def __init__(self, constitution_text: str | None = None) -> None:
        self.constitution_text = constitution_text or (
            "LangGraph Dev Squad runs a planner-owned SDD workflow and blocks repo writes "
            "until readiness, tests, review, and pre-PR guards have passed."
        )

    def load_for_run(
        self, tenant_id: str, repo_id: str, config_snapshot_id: str
    ) -> RuntimeArtifact:
        return RuntimeArtifact(
            kind=ArtifactKind.CONSTITUTION,
            summary=(
                f"{self.constitution_text} tenant={tenant_id} repo={repo_id} "
                f"snapshot={config_snapshot_id}"
            ),
        )


class RuleBasedPlannerArtifactService:
    def create_feature_spec(
        self, run: TicketRunState, planning_request: PlanningRequest, context: ResolvedContextBundle
    ) -> RuntimeArtifact:
        context_sources = ", ".join(entry.source.value for entry in context.entries)
        return RuntimeArtifact(
            kind=ArtifactKind.FEATURE_SPEC,
            summary=(
                f"Ticket {planning_request.ticket_key}: {planning_request.summary}. "
                f"Context order used: {context_sources or 'none'}."
            ),
        )

    def create_clarification_notes(
        self, run: TicketRunState, planning_request: PlanningRequest
    ) -> RuntimeArtifact:
        if planning_request.ambiguous:
            summary = (
                "Ambiguity detected. Clarification stays autonomous-first until the configured "
                "iteration limit is exhausted."
            )
        else:
            summary = "No unresolved ambiguity detected for this ticket."

        return RuntimeArtifact(kind=ArtifactKind.CLARIFICATION_NOTES, summary=summary)

    def create_implementation_plan(
        self, run: TicketRunState, planning_request: PlanningRequest
    ) -> RuntimeArtifact:
        steps = "; ".join(planning_request.implementation_tasks)
        return RuntimeArtifact(
            kind=ArtifactKind.IMPLEMENTATION_PLAN,
            summary=f"Implementation plan for {planning_request.ticket_key}: {steps}",
        )

    def create_task_list(
        self, run: TicketRunState, planning_request: PlanningRequest
    ) -> tuple[TaskListArtifact | None, bool, list[str]]:
        if planning_request.force_missing_task_list:
            return None, False, ["Task list generation was intentionally disabled for this request."]

        tasks: list[TaskItem] = []
        test_targets: list[TestTarget] = []

        for index, title in enumerate(planning_request.implementation_tasks, start=1):
            implementation_id = f"impl-{index}"
            unit_test_id = f"unit-{index}"
            tasks.append(
                TaskItem(
                    task_id=implementation_id,
                    title=title,
                    category="implementation",
                )
            )
            tasks.append(
                TaskItem(
                    task_id=unit_test_id,
                    title=f"Unit coverage for: {title}",
                    category="unit_test",
                    paired_with=implementation_id,
                )
            )
            test_targets.append(TestTarget(name=unit_test_id, kind="unit"))

        if planning_request.public_surface_change:
            tasks.append(
                TaskItem(
                    task_id="e2e-1",
                    title="End-to-end validation for public surface behavior",
                    category="e2e_test",
                )
            )
            test_targets.append(TestTarget(name="e2e-1", kind="e2e"))

        quality_targets = [
            QualityTarget(name=check_name) for check_name in planning_request.design_checks
        ]
        for index, quality_target in enumerate(quality_targets, start=1):
            tasks.append(
                TaskItem(
                    task_id=f"quality-{index}",
                    title=f"Quality gate: {quality_target.name}",
                    category="quality",
                )
            )

        task_list = TaskListArtifact(
            summary=f"Task list for {planning_request.ticket_key}",
            tasks=tasks,
            required_test_targets=test_targets,
            required_quality_checks=quality_targets,
            public_surface_change=planning_request.public_surface_change,
        )
        ready, errors = task_list.validate_for_repo_write()
        if planning_request.force_not_ready:
            ready = False
            errors.append("Readiness was intentionally forced off for this request.")

        return task_list, ready, errors

    @staticmethod
    def build_context_request(
        run: TicketRunState, planning_request: PlanningRequest
    ) -> ContextRequest:
        return ContextRequest(
            available_context={
                ContextSource.JIRA: [f"{planning_request.ticket_key}: {planning_request.summary}"],
                ContextSource.REPOSITORY: [f"Repository scope: {planning_request.repo_id}"],
                ContextSource.RUN_STATE: [f"Run identity: {run.run_id}"],
                ContextSource.FIRST_PARTY: [
                    "Constitution and product contracts from OpenSpec and AGENTS.md"
                ],
            }
        )

    @staticmethod
    def record_artifact_hash(run: TicketRunState, artifact: RuntimeArtifact) -> None:
        run.artifact_hashes[artifact.kind.value] = sha256(artifact.summary.encode("utf-8")).hexdigest()
