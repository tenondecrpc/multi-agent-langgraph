from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from backend.persistence.contracts import HandlerRegistry

if TYPE_CHECKING:
    from backend.persistence.testing.control_plane import InMemoryHandlerRegistry

START_NODE = "START"
END_NODE = "END"
PROTECTED_PROFILE = "ticket_to_pr_v1"
REQUIRED_SYSTEM_NODES = (
    "load_constitution",
    "create_feature_spec",
    "clarify",
    "create_plan",
    "create_task_list",
    "readiness_gate",
    "coder",
    "tester",
    "reviewer",
    "pre_pr_sync",
    "pr_creator",
    "escalate",
)
REQUIRED_PR_PATH_NODES = (
    "readiness_gate",
    "coder",
    "tester",
    "reviewer",
    "pre_pr_sync",
    "pr_creator",
)


class RouteHandlerRef(BaseModel):
    handler_name: str
    handler_version: str
    handler_kind: Literal["system", "tenant_configurable"]


class GraphNodeConfig(BaseModel):
    node_id: str
    handler_name: str
    handler_kind: Literal["system", "tenant_configurable"]
    writes_repo: bool = False
    is_human_approval: bool = False
    terminal: bool = False


class GraphEdgeConfig(BaseModel):
    source: str
    target: str
    transition: Literal["success", "retry", "escalate", "terminal", "break_glass"]
    escalation_reason: str | None = None


class GraphConfigVersion(BaseModel):
    config_version_id: str
    profile_id: str
    graph_nodes: list[GraphNodeConfig]
    graph_edges: list[GraphEdgeConfig]
    route_handlers: list[RouteHandlerRef]
    invariant_profile: Literal["ticket_to_pr_v1"]
    created_by: str
    created_at: datetime


class GraphValidationResult(BaseModel):
    compiles: bool
    invariant_errors: list[str] = Field(default_factory=list)
    missing_escalation_sinks: list[str] = Field(default_factory=list)
    protected_path_violations: list[str] = Field(default_factory=list)


class GraphConfigValidator:
    def __init__(self, *, handler_registry: HandlerRegistry) -> None:
        self.handler_registry = handler_registry

    def validate(
        self,
        config: GraphConfigVersion,
        *,
        registered_escalation_sinks: set[str],
    ) -> GraphValidationResult:
        compile_errors: list[str] = []
        node_index: dict[str, GraphNodeConfig] = {}
        handler_refs = {ref.handler_name: ref for ref in config.route_handlers}

        for node in config.graph_nodes:
            if node.node_id in node_index:
                compile_errors.append(f"Duplicate node id `{node.node_id}`.")
                continue
            node_index[node.node_id] = node

            declared_handler = handler_refs.get(node.handler_name)
            if declared_handler is None:
                compile_errors.append(
                    f"Node `{node.node_id}` references unknown handler `{node.handler_name}`."
                )
                continue
            registered_kind = self.handler_registry.resolve(node.handler_name)
            if registered_kind is None:
                compile_errors.append(
                    f"Handler `{node.handler_name}` is not present in the registry."
                )
            elif registered_kind != node.handler_kind:
                compile_errors.append(
                    f"Handler `{node.handler_name}` kind mismatch for node `{node.node_id}`."
                )

        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in config.graph_edges:
            if edge.source != START_NODE and edge.source not in node_index:
                compile_errors.append(
                    f"Edge source `{edge.source}` is not defined in the graph."
                )
            if edge.target != END_NODE and edge.target not in node_index:
                compile_errors.append(
                    f"Edge target `{edge.target}` is not defined in the graph."
                )
            adjacency[edge.source].append(edge.target)

        if compile_errors:
            return GraphValidationResult(compiles=False, invariant_errors=compile_errors)

        invariant_errors: list[str] = []
        protected_path_violations: list[str] = []
        missing_escalation_sinks: list[str] = []

        if config.invariant_profile == PROTECTED_PROFILE:
            for node_id in REQUIRED_SYSTEM_NODES:
                node = node_index.get(node_id)
                if node is None:
                    invariant_errors.append(
                        f"Protected profile is missing required node `{node_id}`."
                    )
                    continue
                if node.handler_kind != "system" or node.handler_name != node_id:
                    invariant_errors.append(
                        f"Protected node `{node_id}` must remain bound to its system handler."
                    )

            pr_paths = self._paths_to_target(adjacency, target="pr_creator")
            if not pr_paths:
                invariant_errors.append(
                    "No success path reaches `pr_creator`."
                )

            for path in pr_paths:
                for required_node in REQUIRED_PR_PATH_NODES:
                    if required_node not in path:
                        invariant_errors.append(
                            f"PR-reaching path is missing required node `{required_node}`."
                        )
                for node_id in path:
                    node = node_index[node_id]
                    if node.is_human_approval:
                        invariant_errors.append(
                            "Manual approval cannot appear on the normal PR-reaching path."
                        )
                    if node.writes_repo:
                        readiness_index = path.index("readiness_gate") if "readiness_gate" in path else -1
                        if readiness_index == -1 or path.index(node_id) < readiness_index:
                            protected_path_violations.append(
                                f"Repo-writing node `{node_id}` is reachable before `readiness_gate`."
                            )

        for edge in config.graph_edges:
            if edge.transition in {"escalate", "terminal"}:
                if edge.escalation_reason is None:
                    invariant_errors.append(
                        f"Edge `{edge.source}->{edge.target}` must declare an escalation reason."
                    )
                    continue
                if edge.escalation_reason not in registered_escalation_sinks:
                    missing_escalation_sinks.append(edge.escalation_reason)

        return GraphValidationResult(
            compiles=True,
            invariant_errors=sorted(set(invariant_errors)),
            missing_escalation_sinks=sorted(set(missing_escalation_sinks)),
            protected_path_violations=sorted(set(protected_path_violations)),
        )

    def _paths_to_target(
        self,
        adjacency: dict[str, list[str]],
        *,
        target: str,
    ) -> list[list[str]]:
        paths: list[list[str]] = []

        def walk(current: str, path: list[str]) -> None:
            if current == target:
                paths.append(path.copy())
                return
            for next_node in adjacency.get(current, []):
                if next_node == END_NODE or next_node in path:
                    continue
                walk(next_node, [*path, next_node])

        walk(START_NODE, [])
        return paths


__all__ = [
    "END_NODE",
    "GraphConfigValidator",
    "GraphConfigVersion",
    "GraphEdgeConfig",
    "GraphNodeConfig",
    "GraphValidationResult",
    "InMemoryHandlerRegistry",
    "PROTECTED_PROFILE",
    "REQUIRED_PR_PATH_NODES",
    "REQUIRED_SYSTEM_NODES",
    "RouteHandlerRef",
    "START_NODE",
]


def __getattr__(name: str):
    if name == "InMemoryHandlerRegistry":
        from backend.persistence.testing.control_plane import InMemoryHandlerRegistry

        return InMemoryHandlerRegistry
    raise AttributeError(name)
