import pytest

from backend.runtime import (
    ContextRequest,
    ContextSource,
    EscalationReason,
    ExecutionRequest,
    InMemoryRunRepository,
    LocalFirstContextResolver,
    PlanningRequest,
    RunNode,
    RunStatus,
    RuntimeWorkflow,
)


def test_context_resolution_stays_local_first() -> None:
    resolver = LocalFirstContextResolver()
    bundle = resolver.resolve(
        ContextRequest(
            available_context={
                ContextSource.EXTERNAL_RESEARCH: ["External article"],
                ContextSource.JIRA: ["Ticket context"],
                ContextSource.RUN_STATE: ["Checkpoint context"],
                ContextSource.REPOSITORY: ["Repository context"],
                ContextSource.FIRST_PARTY: ["Official documentation"],
            },
            external_research_reason="Earlier sources were insufficient for this scenario.",
        )
    )

    assert [entry.source for entry in bundle.entries] == [
        ContextSource.JIRA,
        ContextSource.REPOSITORY,
        ContextSource.RUN_STATE,
        ContextSource.FIRST_PARTY,
        ContextSource.EXTERNAL_RESEARCH,
    ]


def test_repo_write_gate_blocks_when_task_list_is_missing() -> None:
    workflow = RuntimeWorkflow()
    run = workflow.execute(
        planning_request=PlanningRequest(
            summary="Attempt repo write without a task list",
            force_missing_task_list=True,
        )
    )

    assert run.status == RunStatus.PAUSED
    assert run.paused_at_node == RunNode.READINESS_GATE
    assert run.escalation_reason == EscalationReason.INVALID_ROUTE_ATTEMPT
    assert run.pr_created is False


def test_success_path_creates_pr_when_guards_pass() -> None:
    workflow = RuntimeWorkflow()
    run = workflow.execute(
        planning_request=PlanningRequest(
            summary="Create the runtime success path",
            implementation_tasks=["Implement planner-owned artifact flow"],
            public_surface_change=True,
        ),
        execution_request=ExecutionRequest(),
    )

    assert run.spec_ready_for_implementation is True
    assert run.tests_passed is True
    assert run.review_approved is True
    assert run.pre_pr_sync_passed is True
    assert run.pr_created is True
    assert run.status == RunStatus.COMPLETED


def test_required_test_failures_retry_then_pause() -> None:
    workflow = RuntimeWorkflow()
    run = workflow.execute(
        planning_request=PlanningRequest(
            summary="Fail required tests until retry budget is exhausted",
            max_test_retries=1,
        ),
        execution_request=ExecutionRequest(test_failures_before_pass=2),
    )

    assert run.status == RunStatus.PAUSED
    assert run.paused_at_node == RunNode.TESTER
    assert run.escalation_reason == EscalationReason.MISSING_OR_FAILING_REQUIRED_TESTS
    assert run.test_retry_count == 1
    assert run.pr_created is False


def test_review_quality_failures_block_approval() -> None:
    workflow = RuntimeWorkflow()
    run = workflow.execute(
        planning_request=PlanningRequest(
            summary="Fail quality review until review retry budget is exhausted",
            max_review_retries=1,
        ),
        execution_request=ExecutionRequest(quality_failures_before_pass=2),
    )

    assert run.status == RunStatus.PAUSED
    assert run.paused_at_node == RunNode.REVIEWER
    assert run.escalation_reason == EscalationReason.REVIEW_BUDGET_EXHAUSTED
    assert run.review_approved is False


def test_pre_pr_sync_blocks_merge_conflicts() -> None:
    workflow = RuntimeWorkflow()
    run = workflow.execute(
        planning_request=PlanningRequest(summary="Catch merge conflicts before PR creation"),
        execution_request=ExecutionRequest(merge_conflict=True),
    )

    assert run.status == RunStatus.PAUSED
    assert run.paused_at_node == RunNode.PRE_PR_SYNC
    assert run.escalation_reason == EscalationReason.MERGE_CONFLICT_DETECTED
    assert run.pr_created is False


def test_escalation_sink_coverage_is_required() -> None:
    repository = InMemoryRunRepository()

    with pytest.raises(ValueError):
        repository.validate_escalation_sinks(
            {
                EscalationReason.UNRESOLVED_AMBIGUITY.value: "ops://clarification",
            }
        )


def test_pause_and_resume_preserve_run_identity() -> None:
    workflow = RuntimeWorkflow()
    paused = workflow.execute(
        planning_request=PlanningRequest(
            summary="Pause on unresolved ambiguity",
            ambiguous=True,
            clarification_resolution_attempt=None,
            max_clarification_iterations=1,
        )
    )

    assert paused.status == RunStatus.PAUSED
    assert paused.escalation_reason == EscalationReason.UNRESOLVED_AMBIGUITY

    resumed = workflow.resume(paused.thread_id)
    assert resumed.run_id == paused.run_id
    assert resumed.thread_id == paused.thread_id
    assert resumed.config_snapshot_id == paused.config_snapshot_id
    assert resumed.escalation_reason is None
    assert resumed.paused_at_node is None
