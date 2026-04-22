from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.persistence.contracts import RunRepository
from backend.persistence.factory import build_persistence_adapters

from .context import LocalFirstContextResolver
from .models import (
    EscalationReason,
    ExecutionRequest,
    PlanningRequest,
    RunNode,
    RunStatus,
    TenantContext,
    TicketRunState,
)
from .planner import RuleBasedPlannerArtifactService, StaticConstitutionLoader


class WorkflowState(TypedDict):
    planning_request: PlanningRequest
    execution_request: ExecutionRequest
    escalation_sinks: dict[str, str]
    run: TicketRunState


class RuntimeWorkflow:
    def __init__(
        self,
        *,
        constitution_loader: StaticConstitutionLoader | None = None,
        planner: RuleBasedPlannerArtifactService | None = None,
        context_resolver: LocalFirstContextResolver | None = None,
        repository: RunRepository | None = None,
    ) -> None:
        self.constitution_loader = constitution_loader or StaticConstitutionLoader()
        self.planner = planner or RuleBasedPlannerArtifactService()
        self.context_resolver = context_resolver or LocalFirstContextResolver()
        self.repository = repository or build_persistence_adapters().run_repository
        self.graph = self._build_graph()

    def execute(
        self,
        *,
        planning_request: PlanningRequest,
        execution_request: ExecutionRequest | None = None,
        escalation_sinks: dict[str, str] | None = None,
    ) -> TicketRunState:
        execution = execution_request or ExecutionRequest()
        sinks = escalation_sinks or self.default_escalation_sinks()
        self.repository.validate_escalation_sinks(sinks)

        run = TicketRunState.new(planning_request)
        state: WorkflowState = {
            "planning_request": planning_request,
            "execution_request": execution,
            "escalation_sinks": sinks,
            "run": run,
        }
        result = self.graph.invoke(state)
        final_run = self.repository.save(result["run"])
        return final_run

    def resume(
        self,
        thread_id: str,
        *,
        tenant_context: TenantContext | None = None,
    ) -> TicketRunState:
        return self.repository.resume(thread_id, tenant_context=tenant_context)

    @staticmethod
    def default_escalation_sinks() -> dict[str, str]:
        return {
            EscalationReason.UNRESOLVED_AMBIGUITY.value: "ops://clarification",
            EscalationReason.TEST_RETRY_BUDGET_EXHAUSTED.value: "ops://testing",
            EscalationReason.REVIEW_BUDGET_EXHAUSTED.value: "ops://review",
            EscalationReason.MISSING_OR_FAILING_REQUIRED_TESTS.value: "ops://quality",
            EscalationReason.DIFF_TOO_LARGE.value: "ops://diff-guard",
            EscalationReason.MERGE_CONFLICT_DETECTED.value: "ops://merge-conflict",
            EscalationReason.INVALID_ROUTE_ATTEMPT.value: "ops://workflow-guard",
            EscalationReason.MISSING_ESCALATION_SINK.value: "ops://workflow-guard",
            EscalationReason.BUDGET_EXHAUSTED.value: "ops://budgeting",
            EscalationReason.ALL_PROVIDERS_UNAVAILABLE.value: "ops://llm-routing",
            EscalationReason.PROVIDER_FAILOVER_EXHAUSTED.value: "ops://llm-routing",
            EscalationReason.ORPHANED_BUDGET_RESERVATION_DETECTED.value: "ops://budgeting",
            EscalationReason.BILLING_RECONCILIATION_DRIFT.value: "ops://metering",
        }

    def _build_graph(self):
        workflow = StateGraph(WorkflowState)

        workflow.add_node("load_constitution", self._load_constitution)
        workflow.add_node("create_feature_spec", self._create_feature_spec)
        workflow.add_node("clarify", self._clarify)
        workflow.add_node("create_plan", self._create_plan)
        workflow.add_node("create_task_list", self._create_task_list)
        workflow.add_node("readiness_gate", self._readiness_gate)
        workflow.add_node("coder", self._coder)
        workflow.add_node("tester", self._tester)
        workflow.add_node("reviewer", self._reviewer)
        workflow.add_node("pre_pr_sync", self._pre_pr_sync)
        workflow.add_node("pr_creator", self._pr_creator)
        workflow.add_node("escalate", self._escalate)

        workflow.add_edge(START, "load_constitution")
        workflow.add_edge("load_constitution", "create_feature_spec")
        workflow.add_edge("create_feature_spec", "clarify")
        workflow.add_conditional_edges(
            "clarify",
            self._route_after_clarification,
            {
                "clarify": "clarify",
                "create_plan": "create_plan",
                "escalate": "escalate",
            },
        )
        workflow.add_edge("create_plan", "create_task_list")
        workflow.add_edge("create_task_list", "readiness_gate")
        workflow.add_conditional_edges(
            "readiness_gate",
            self._route_after_readiness_gate,
            {"coder": "coder", "escalate": "escalate"},
        )
        workflow.add_edge("coder", "tester")
        workflow.add_conditional_edges(
            "tester",
            self._route_after_tester,
            {
                "coder": "coder",
                "reviewer": "reviewer",
                "escalate": "escalate",
            },
        )
        workflow.add_conditional_edges(
            "reviewer",
            self._route_after_reviewer,
            {
                "coder": "coder",
                "pre_pr_sync": "pre_pr_sync",
                "escalate": "escalate",
            },
        )
        workflow.add_conditional_edges(
            "pre_pr_sync",
            self._route_after_pre_pr_sync,
            {"pr_creator": "pr_creator", "escalate": "escalate"},
        )
        workflow.add_conditional_edges(
            "pr_creator",
            self._route_after_pr_creator,
            {"complete": END, "escalate": "escalate"},
        )
        workflow.add_edge("escalate", END)
        return workflow.compile()

    def _load_constitution(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        run.transition_to(RunNode.LOAD_CONSTITUTION)
        run.constitution = self.constitution_loader.load_for_run(
            run.tenant_id, run.repo_id, run.config_snapshot_id
        )
        self.planner.record_artifact_hash(run, run.constitution)
        return {"run": run}

    def _create_feature_spec(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        planning_request = state["planning_request"]
        run.transition_to(RunNode.CREATE_FEATURE_SPEC)
        context_request = self.planner.build_context_request(run, planning_request)
        context_bundle = self.context_resolver.resolve(context_request)
        run.feature_spec = self.planner.create_feature_spec(run, planning_request, context_bundle)
        self.planner.record_artifact_hash(run, run.feature_spec)
        return {"run": run}

    def _clarify(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        planning_request = state["planning_request"]
        run.transition_to(RunNode.CLARIFY)

        if run.clarification_notes is None:
            run.clarification_notes = self.planner.create_clarification_notes(run, planning_request)
            self.planner.record_artifact_hash(run, run.clarification_notes)

        if not planning_request.ambiguous:
            run.clarification_complete = True
            return {"run": run}

        run.clarification_attempts += 1
        resolution_attempt = planning_request.clarification_resolution_attempt

        if resolution_attempt is not None and run.clarification_attempts >= resolution_attempt:
            run.clarification_complete = True
            return {"run": run}

        if run.clarification_attempts >= run.max_clarification_iterations:
            run.escalation_reason = EscalationReason.UNRESOLVED_AMBIGUITY
            run.paused_at_node = RunNode.CLARIFY
            return {"run": run}

        run.last_retry_reason = "clarification_retry"
        return {"run": run}

    def _create_plan(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        planning_request = state["planning_request"]
        run.transition_to(RunNode.CREATE_PLAN)
        run.implementation_plan = self.planner.create_implementation_plan(run, planning_request)
        self.planner.record_artifact_hash(run, run.implementation_plan)
        return {"run": run}

    def _create_task_list(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        planning_request = state["planning_request"]
        run.transition_to(RunNode.CREATE_TASK_LIST)
        task_list, ready, errors = self.planner.create_task_list(run, planning_request)
        run.task_list = task_list
        run.spec_ready_for_implementation = ready
        run.readiness_errors = errors

        if task_list is not None:
            run.required_test_targets = task_list.required_test_targets
            run.required_quality_checks = task_list.required_quality_checks
            self.planner.record_artifact_hash(run, task_list)

        return {"run": run}

    def _readiness_gate(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        run.transition_to(RunNode.READINESS_GATE)
        if run.task_list is None or not run.spec_ready_for_implementation:
            run.escalation_reason = EscalationReason.INVALID_ROUTE_ATTEMPT
            run.paused_at_node = RunNode.READINESS_GATE
            return {"run": run}

        run.status = RunStatus.ACTIVE
        return {"run": run}

    def _coder(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        run.transition_to(RunNode.CODER)
        run.status = RunStatus.ACTIVE
        return {"run": run}

    def _tester(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        execution_request = state["execution_request"]
        run.transition_to(RunNode.TESTER)

        missing_or_skipped = execution_request.missing_required_tests or execution_request.skip_required_tests
        should_fail_tests = run.test_retry_count < execution_request.test_failures_before_pass
        missing_declared_targets = not run.required_test_targets

        if missing_or_skipped or should_fail_tests or missing_declared_targets:
            if run.test_retry_count >= run.max_test_retries:
                run.escalation_reason = EscalationReason.MISSING_OR_FAILING_REQUIRED_TESTS
                run.paused_at_node = RunNode.TESTER
                return {"run": run}

            run.test_retry_count += 1
            run.last_retry_reason = EscalationReason.MISSING_OR_FAILING_REQUIRED_TESTS.value
            run.tests_passed = False
            return {"run": run}

        run.tests_passed = True
        return {"run": run}

    def _reviewer(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        execution_request = state["execution_request"]
        run.transition_to(RunNode.REVIEWER)

        if not run.tests_passed:
            run.escalation_reason = EscalationReason.INVALID_ROUTE_ATTEMPT
            run.paused_at_node = RunNode.REVIEWER
            return {"run": run}

        should_fail_quality = run.review_retry_count < execution_request.quality_failures_before_pass

        if should_fail_quality:
            if run.review_retry_count >= run.max_review_retries:
                run.escalation_reason = EscalationReason.REVIEW_BUDGET_EXHAUSTED
                run.paused_at_node = RunNode.REVIEWER
                return {"run": run}

            run.review_retry_count += 1
            run.last_retry_reason = EscalationReason.REVIEW_BUDGET_EXHAUSTED.value
            run.review_approved = False
            run.quality_checks_passed = False
            return {"run": run}

        run.quality_checks_passed = True
        run.review_approved = True
        return {"run": run}

    def _pre_pr_sync(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        execution_request = state["execution_request"]
        run.transition_to(RunNode.PRE_PR_SYNC)

        if execution_request.diff_too_large:
            run.escalation_reason = EscalationReason.DIFF_TOO_LARGE
            run.paused_at_node = RunNode.PRE_PR_SYNC
            return {"run": run}

        if execution_request.merge_conflict:
            run.escalation_reason = EscalationReason.MERGE_CONFLICT_DETECTED
            run.paused_at_node = RunNode.PRE_PR_SYNC
            return {"run": run}

        run.pre_pr_sync_passed = True
        return {"run": run}

    def _pr_creator(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        run.transition_to(RunNode.PR_CREATOR)

        if not (run.tests_passed and run.review_approved and run.pre_pr_sync_passed):
            run.escalation_reason = EscalationReason.INVALID_ROUTE_ATTEMPT
            run.paused_at_node = RunNode.PR_CREATOR
            return {"run": run}

        run.pr_created = True
        run.status = RunStatus.COMPLETED
        return {"run": run}

    def _escalate(self, state: WorkflowState) -> dict[str, TicketRunState]:
        run = state["run"]
        escalation_sinks = state["escalation_sinks"]
        run.transition_to(RunNode.ESCALATE)
        run.status = RunStatus.PAUSED

        if run.escalation_reason is None:
            run.escalation_reason = EscalationReason.MISSING_ESCALATION_SINK
            run.paused_at_node = run.paused_at_node or RunNode.ESCALATE

        sink = escalation_sinks.get(run.escalation_reason.value)
        if sink is None:
            run.escalation_reason = EscalationReason.MISSING_ESCALATION_SINK
            run.escalation_sink = None
        else:
            run.escalation_sink = sink

        return {"run": run}

    @staticmethod
    def _route_after_clarification(state: WorkflowState) -> str:
        run = state["run"]
        if run.escalation_reason is not None:
            return "escalate"
        if run.clarification_complete:
            return "create_plan"
        return "clarify"

    @staticmethod
    def _route_after_readiness_gate(state: WorkflowState) -> str:
        run = state["run"]
        if run.escalation_reason is not None:
            return "escalate"
        return "coder"

    @staticmethod
    def _route_after_tester(state: WorkflowState) -> str:
        run = state["run"]
        if run.escalation_reason is not None:
            return "escalate"
        if run.tests_passed:
            return "reviewer"
        return "coder"

    @staticmethod
    def _route_after_reviewer(state: WorkflowState) -> str:
        run = state["run"]
        if run.escalation_reason is not None:
            return "escalate"
        if run.review_approved:
            return "pre_pr_sync"
        return "coder"

    @staticmethod
    def _route_after_pre_pr_sync(state: WorkflowState) -> str:
        run = state["run"]
        if run.escalation_reason is not None:
            return "escalate"
        return "pr_creator"

    @staticmethod
    def _route_after_pr_creator(state: WorkflowState) -> str:
        run = state["run"]
        if run.pr_created:
            return "complete"
        return "escalate"
