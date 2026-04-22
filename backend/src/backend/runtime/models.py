from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArtifactKind(StrEnum):
    CONSTITUTION = "constitution"
    FEATURE_SPEC = "feature_spec"
    CLARIFICATION_NOTES = "clarification_notes"
    IMPLEMENTATION_PLAN = "implementation_plan"
    TASK_LIST = "task_list"


class ContextSource(StrEnum):
    JIRA = "jira"
    REPOSITORY = "repository"
    RUN_STATE = "run_state"
    INTERNAL_KNOWLEDGE = "internal_knowledge"
    FIRST_PARTY = "first_party"
    EXTERNAL_RESEARCH = "external_research"


class RunNode(StrEnum):
    INTAKE = "intake"
    LOAD_CONSTITUTION = "load_constitution"
    CREATE_FEATURE_SPEC = "create_feature_spec"
    CLARIFY = "clarify"
    CREATE_PLAN = "create_plan"
    CREATE_TASK_LIST = "create_task_list"
    READINESS_GATE = "readiness_gate"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    PRE_PR_SYNC = "pre_pr_sync"
    PR_CREATOR = "pr_creator"
    ESCALATE = "escalate"


class RunStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class EscalationReason(StrEnum):
    UNRESOLVED_AMBIGUITY = "unresolved_ambiguity"
    TEST_RETRY_BUDGET_EXHAUSTED = "test_retry_budget_exhausted"
    REVIEW_BUDGET_EXHAUSTED = "review_budget_exhausted"
    MISSING_OR_FAILING_REQUIRED_TESTS = "missing_or_failing_required_tests"
    DIFF_TOO_LARGE = "diff_too_large"
    MERGE_CONFLICT_DETECTED = "merge_conflict_detected"
    INVALID_ROUTE_ATTEMPT = "invalid_route_attempt"
    MISSING_ESCALATION_SINK = "missing_escalation_sink"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ALL_PROVIDERS_UNAVAILABLE = "all_providers_unavailable"
    PROVIDER_FAILOVER_EXHAUSTED = "provider_failover_exhausted"
    ORPHANED_BUDGET_RESERVATION_DETECTED = "orphaned_budget_reservation_detected"
    BILLING_RECONCILIATION_DRIFT = "billing_reconciliation_drift"


class TenantContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    team_id: str


class RuntimeArtifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    kind: ArtifactKind
    summary: str
    version: int = 1


class TaskItem(BaseModel):
    task_id: str
    title: str
    category: Literal["implementation", "unit_test", "e2e_test", "quality"]
    paired_with: str | None = None


class TestTarget(BaseModel):
    name: str
    kind: Literal["unit", "e2e"]


class QualityTarget(BaseModel):
    name: str


class TaskListArtifact(RuntimeArtifact):
    tasks: list[TaskItem]
    required_test_targets: list[TestTarget] = Field(default_factory=list)
    required_quality_checks: list[QualityTarget] = Field(default_factory=list)
    public_surface_change: bool = False

    kind: ArtifactKind = ArtifactKind.TASK_LIST

    def validate_for_repo_write(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        implementation_task_ids = {
            task.task_id for task in self.tasks if task.category == "implementation"
        }
        paired_unit_tests = {
            task.paired_with for task in self.tasks if task.category == "unit_test" and task.paired_with
        }

        for task_id in implementation_task_ids:
            if task_id not in paired_unit_tests:
                errors.append(f"Implementation task `{task_id}` is missing a paired unit test task.")

        if self.public_surface_change and not any(
            target.kind == "e2e" for target in self.required_test_targets
        ):
            errors.append("Public-surface changes require an end-to-end test target.")

        if not self.required_quality_checks:
            errors.append("At least one quality check must be declared before repo-write readiness.")

        if not implementation_task_ids:
            errors.append("At least one implementation task is required.")

        return not errors, errors


class PlanningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = "tenant-alpha"
    team_id: str = "team-core"
    repo_id: str = "repo-dev-squad"
    ticket_key: str = "ENG-1"
    summary: str
    implementation_tasks: list[str] = Field(
        default_factory=lambda: ["Implement the requested change and supporting tests."]
    )
    ambiguous: bool = False
    clarification_resolution_attempt: int | None = 1
    public_surface_change: bool = False
    design_checks: list[str] = Field(
        default_factory=lambda: ["lint", "type_check", "solid_review"]
    )
    config_snapshot_id: str = "config-v1"
    graph_profile_id: str = "ticket_to_pr_v1"
    catalog_version: str = "catalog-v1"
    max_clarification_iterations: int = 2
    max_test_retries: int = 2
    max_review_retries: int = 1
    force_missing_task_list: bool = False
    force_not_ready: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_ticket_id(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        ticket_key = normalized.get("ticket_key")
        ticket_id = normalized.pop("ticket_id", None)

        if ticket_key is not None and ticket_id is not None and ticket_key != ticket_id:
            raise ValueError("`ticket_key` and `ticket_id` must match when both are provided.")

        if ticket_key is None and ticket_id is not None:
            normalized["ticket_key"] = ticket_id

        return normalized


class ExecutionRequest(BaseModel):
    test_failures_before_pass: int = 0
    quality_failures_before_pass: int = 0
    missing_required_tests: bool = False
    skip_required_tests: bool = False
    diff_too_large: bool = False
    merge_conflict: bool = False


class ResolvedContextEntry(BaseModel):
    source: ContextSource
    content: str
    provenance: str


class ResolvedContextBundle(BaseModel):
    entries: list[ResolvedContextEntry]
    external_research_reason: str | None = None


class ContextRequest(BaseModel):
    available_context: dict[ContextSource, list[str]] = Field(default_factory=dict)
    external_research_reason: str | None = None


class TicketRunState(BaseModel):
    tenant_id: str
    team_id: str
    repo_id: str
    ticket_key: str
    run_id: str
    thread_id: str
    config_snapshot_id: str
    graph_profile_id: str
    catalog_version: str

    constitution: RuntimeArtifact | None = None
    feature_spec: RuntimeArtifact | None = None
    clarification_notes: RuntimeArtifact | None = None
    implementation_plan: RuntimeArtifact | None = None
    task_list: TaskListArtifact | None = None
    artifact_hashes: dict[str, str] = Field(default_factory=dict)

    status: RunStatus = RunStatus.PLANNING
    current_node: RunNode = RunNode.INTAKE
    node_history: list[RunNode] = Field(default_factory=lambda: [RunNode.INTAKE])
    paused_at_node: RunNode | None = None
    escalation_reason: EscalationReason | None = None
    escalation_sink: str | None = None

    clarification_attempts: int = 0
    max_clarification_iterations: int = 2
    clarification_complete: bool = False

    spec_ready_for_implementation: bool = False
    required_test_targets: list[TestTarget] = Field(default_factory=list)
    required_quality_checks: list[QualityTarget] = Field(default_factory=list)
    readiness_errors: list[str] = Field(default_factory=list)

    test_retry_count: int = 0
    max_test_retries: int = 2
    tests_passed: bool = False

    review_retry_count: int = 0
    max_review_retries: int = 1
    quality_checks_passed: bool = False
    review_approved: bool = False

    pre_pr_sync_passed: bool = False
    pr_created: bool = False
    last_retry_reason: str | None = None
    state_schema_version: str = "1"

    @classmethod
    def new(cls, planning_request: PlanningRequest) -> TicketRunState:
        run_id = str(uuid4())
        return cls(
            tenant_id=planning_request.tenant_id,
            team_id=planning_request.team_id,
            repo_id=planning_request.repo_id,
            ticket_key=planning_request.ticket_key,
            run_id=run_id,
            thread_id=f"{planning_request.tenant_id}:{planning_request.ticket_key}:{run_id}",
            config_snapshot_id=planning_request.config_snapshot_id,
            graph_profile_id=planning_request.graph_profile_id,
            catalog_version=planning_request.catalog_version,
            max_clarification_iterations=planning_request.max_clarification_iterations,
            max_test_retries=planning_request.max_test_retries,
            max_review_retries=planning_request.max_review_retries,
        )

    def clear_pause(self) -> TicketRunState:
        self.paused_at_node = None
        self.escalation_reason = None
        self.escalation_sink = None
        if self.status == RunStatus.PAUSED:
            self.status = RunStatus.ACTIVE
        return self

    def transition_to(self, node: RunNode) -> TicketRunState:
        self.current_node = node
        self.node_history.append(node)
        return self
