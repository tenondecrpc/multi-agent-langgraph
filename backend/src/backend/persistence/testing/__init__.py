__all__ = [
    "InMemoryBudgetLedger",
    "InMemoryControlPlaneStore",
    "InMemoryHandlerRegistry",
    "InMemoryMeteringLedger",
    "InMemoryModelCatalog",
    "InMemoryProviderHealthStore",
    "InMemoryRunRepository",
    "InMemoryWebhookGuard",
    "InMemoryWorkerController",
    "required_phase_one_escalation_reasons",
]


def __getattr__(name: str):
    if name in {"InMemoryRunRepository", "required_phase_one_escalation_reasons"}:
        from .runtime import InMemoryRunRepository, required_phase_one_escalation_reasons

        exports = {
            "InMemoryRunRepository": InMemoryRunRepository,
            "required_phase_one_escalation_reasons": required_phase_one_escalation_reasons,
        }
        return exports[name]
    if name in {"InMemoryControlPlaneStore", "InMemoryHandlerRegistry"}:
        from .control_plane import InMemoryControlPlaneStore, InMemoryHandlerRegistry

        exports = {
            "InMemoryControlPlaneStore": InMemoryControlPlaneStore,
            "InMemoryHandlerRegistry": InMemoryHandlerRegistry,
        }
        return exports[name]
    if name == "InMemoryWorkerController":
        from .worker import InMemoryWorkerController

        return InMemoryWorkerController
    if name in {
        "InMemoryBudgetLedger",
        "InMemoryMeteringLedger",
        "InMemoryModelCatalog",
        "InMemoryProviderHealthStore",
    }:
        from .governance import (
            InMemoryBudgetLedger,
            InMemoryMeteringLedger,
            InMemoryModelCatalog,
            InMemoryProviderHealthStore,
        )

        exports = {
            "InMemoryBudgetLedger": InMemoryBudgetLedger,
            "InMemoryMeteringLedger": InMemoryMeteringLedger,
            "InMemoryModelCatalog": InMemoryModelCatalog,
            "InMemoryProviderHealthStore": InMemoryProviderHealthStore,
        }
        return exports[name]
    if name == "InMemoryWebhookGuard":
        from .security import InMemoryWebhookGuard

        return InMemoryWebhookGuard
    raise AttributeError(name)
