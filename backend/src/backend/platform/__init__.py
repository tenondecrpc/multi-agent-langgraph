from __future__ import annotations

from importlib import import_module

__all__ = [
    "DeadLetterRecord",
    "InMemoryWorkerController",
    "QueuedJob",
    "SandboxJobTemplate",
    "SandboxTemplateBuilder",
    "WeightedFairDispatcher",
    "WorkerDrainLease",
    "WorkerPoolProfile",
    "build_platform_routers",
    "route_inventory",
]

_EXPORTS = {
    "DeadLetterRecord": (".queue", "DeadLetterRecord"),
    "InMemoryWorkerController": (".queue", "InMemoryWorkerController"),
    "QueuedJob": (".queue", "QueuedJob"),
    "SandboxJobTemplate": (".sandbox", "SandboxJobTemplate"),
    "SandboxTemplateBuilder": (".sandbox", "SandboxTemplateBuilder"),
    "WeightedFairDispatcher": (".queue", "WeightedFairDispatcher"),
    "WorkerDrainLease": (".queue", "WorkerDrainLease"),
    "WorkerPoolProfile": (".sandbox", "WorkerPoolProfile"),
    "build_platform_routers": (".api", "build_platform_routers"),
    "route_inventory": (".api", "route_inventory"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name, __name__)
    return getattr(module, attr_name)
