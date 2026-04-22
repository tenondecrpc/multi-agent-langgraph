from __future__ import annotations

from importlib import import_module

__all__ = [
    "ContextRequest",
    "ContextSource",
    "EscalationReason",
    "ExecutionRequest",
    "LocalFirstContextResolver",
    "PlanningRequest",
    "ResolvedContextBundle",
    "ResolvedContextEntry",
    "RuleBasedPlannerArtifactService",
    "RunNode",
    "RunStatus",
    "RuntimeArtifact",
    "RuntimeWorkflow",
    "StaticConstitutionLoader",
    "TaskItem",
    "TaskListArtifact",
    "TenantContext",
    "TestTarget",
    "TicketRunState",
    "required_phase_one_escalation_reasons",
]

_EXPORTS = {
    "ContextRequest": (".models", "ContextRequest"),
    "ContextSource": (".models", "ContextSource"),
    "EscalationReason": (".models", "EscalationReason"),
    "ExecutionRequest": (".models", "ExecutionRequest"),
    "LocalFirstContextResolver": (".context", "LocalFirstContextResolver"),
    "PlanningRequest": (".models", "PlanningRequest"),
    "ResolvedContextBundle": (".models", "ResolvedContextBundle"),
    "ResolvedContextEntry": (".models", "ResolvedContextEntry"),
    "RuleBasedPlannerArtifactService": (".planner", "RuleBasedPlannerArtifactService"),
    "RunNode": (".models", "RunNode"),
    "RunStatus": (".models", "RunStatus"),
    "RuntimeArtifact": (".models", "RuntimeArtifact"),
    "RuntimeWorkflow": (".workflow", "RuntimeWorkflow"),
    "StaticConstitutionLoader": (".planner", "StaticConstitutionLoader"),
    "TaskItem": (".models", "TaskItem"),
    "TaskListArtifact": (".models", "TaskListArtifact"),
    "TenantContext": (".models", "TenantContext"),
    "TestTarget": (".models", "TestTarget"),
    "TicketRunState": (".models", "TicketRunState"),
    "required_phase_one_escalation_reasons": (".store", "required_phase_one_escalation_reasons"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name, __name__)
    return getattr(module, attr_name)
