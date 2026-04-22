from __future__ import annotations

from importlib import import_module

__all__ = [
    "ActivationThresholds",
    "AgentConfigVersion",
    "AgentConfigValidator",
    "AgentDryRunResult",
    "AgentValidationResult",
    "AuditEvent",
    "ComparisonMetrics",
    "ConfigSnapshot",
    "ConfigVersionRecord",
    "ControlPlaneConflictError",
    "GraphConfigValidator",
    "GraphConfigVersion",
    "GraphEdgeConfig",
    "GraphNodeConfig",
    "GraphValidationResult",
    "InMemoryControlPlaneStore",
    "InMemoryHandlerRegistry",
    "RouteHandlerRef",
    "RunSnapshotBinding",
    "ShadowComparisonReport",
    "ShadowIsolationProfile",
    "ShadowModeEvaluator",
    "default_agent_configs",
]

_EXPORTS = {
    "ActivationThresholds": (".shadow", "ActivationThresholds"),
    "AgentConfigVersion": (".agents", "AgentConfigVersion"),
    "AgentConfigValidator": (".agents", "AgentConfigValidator"),
    "AgentDryRunResult": (".agents", "AgentDryRunResult"),
    "AgentValidationResult": (".agents", "AgentValidationResult"),
    "AuditEvent": (".store", "AuditEvent"),
    "ComparisonMetrics": (".shadow", "ComparisonMetrics"),
    "ConfigSnapshot": (".store", "ConfigSnapshot"),
    "ConfigVersionRecord": (".store", "ConfigVersionRecord"),
    "ControlPlaneConflictError": (".store", "ControlPlaneConflictError"),
    "GraphConfigValidator": (".graph", "GraphConfigValidator"),
    "GraphConfigVersion": (".graph", "GraphConfigVersion"),
    "GraphEdgeConfig": (".graph", "GraphEdgeConfig"),
    "GraphNodeConfig": (".graph", "GraphNodeConfig"),
    "GraphValidationResult": (".graph", "GraphValidationResult"),
    "InMemoryControlPlaneStore": (".store", "InMemoryControlPlaneStore"),
    "InMemoryHandlerRegistry": (".graph", "InMemoryHandlerRegistry"),
    "RouteHandlerRef": (".graph", "RouteHandlerRef"),
    "RunSnapshotBinding": (".store", "RunSnapshotBinding"),
    "ShadowComparisonReport": (".shadow", "ShadowComparisonReport"),
    "ShadowIsolationProfile": (".shadow", "ShadowIsolationProfile"),
    "ShadowModeEvaluator": (".shadow", "ShadowModeEvaluator"),
    "default_agent_configs": (".agents", "default_agent_configs"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name, __name__)
    return getattr(module, attr_name)
