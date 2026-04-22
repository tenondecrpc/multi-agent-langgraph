from __future__ import annotations

from collections.abc import Mapping

from backend.runtime.models import EscalationReason, RunNode, RunStatus, TenantContext, TicketRunState


def required_phase_one_escalation_reasons() -> tuple[EscalationReason, ...]:
    return (
        EscalationReason.UNRESOLVED_AMBIGUITY,
        EscalationReason.TEST_RETRY_BUDGET_EXHAUSTED,
        EscalationReason.REVIEW_BUDGET_EXHAUSTED,
        EscalationReason.MISSING_OR_FAILING_REQUIRED_TESTS,
        EscalationReason.DIFF_TOO_LARGE,
        EscalationReason.MERGE_CONFLICT_DETECTED,
        EscalationReason.INVALID_ROUTE_ATTEMPT,
        EscalationReason.MISSING_ESCALATION_SINK,
    )


class InMemoryRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, TicketRunState] = {}

    def save(self, run: TicketRunState) -> TicketRunState:
        snapshot = run.model_copy(deep=True)
        self._runs[snapshot.thread_id] = snapshot
        return snapshot

    def load(
        self,
        thread_id: str,
        *,
        tenant_context: TenantContext | None = None,
    ) -> TicketRunState | None:
        snapshot = self._runs.get(thread_id)
        if snapshot is None:
            return None
        if tenant_context is not None and (
            snapshot.tenant_id != tenant_context.tenant_id
            or snapshot.team_id != tenant_context.team_id
        ):
            return None
        return snapshot.model_copy(deep=True)

    def validate_escalation_sinks(
        self,
        escalation_sinks: Mapping[str, str],
        required_reasons: tuple[EscalationReason, ...] | None = None,
    ) -> None:
        reasons = required_reasons or required_phase_one_escalation_reasons()
        missing = [reason.value for reason in reasons if reason.value not in escalation_sinks]
        if missing:
            raise ValueError(
                "Every phase-1 escalation reason must map to a registered sink. "
                f"Missing: {', '.join(sorted(missing))}"
            )

    def pause(
        self,
        run: TicketRunState,
        node: RunNode,
        reason: EscalationReason,
        escalation_sinks: Mapping[str, str],
    ) -> TicketRunState:
        self.validate_escalation_sinks(escalation_sinks)
        paused = run.model_copy(deep=True)
        paused.status = RunStatus.PAUSED
        paused.paused_at_node = node
        paused.escalation_reason = reason
        paused.escalation_sink = escalation_sinks[reason.value]
        return self.save(paused)

    def resume(
        self,
        thread_id: str,
        *,
        tenant_context: TenantContext | None = None,
    ) -> TicketRunState:
        run = self.load(thread_id, tenant_context=tenant_context)
        if run is None:
            raise KeyError(f"No run found for thread `{thread_id}`.")

        run.clear_pause()
        return self.save(run)
