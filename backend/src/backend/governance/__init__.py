from __future__ import annotations

from importlib import import_module

__all__ = [
    "BudgetBalance",
    "BudgetCaps",
    "BudgetContext",
    "BudgetExceededError",
    "BudgetReservation",
    "BudgetSettlement",
    "HourlyUsageRollup",
    "InMemoryBudgetLedger",
    "InMemoryMeteringLedger",
    "InMemoryModelCatalog",
    "InMemoryProviderHealthStore",
    "MeteringExportRequest",
    "ModelCatalogEntry",
    "OrphanedReservationRelease",
    "ProviderHealthSnapshot",
    "ProviderHealthState",
    "ProviderRoutingError",
    "ProviderSelection",
    "ReconciliationResult",
    "RoleModelAssignment",
    "RoleTokenPolicy",
    "RuleBasedProviderRouter",
    "TokenCap",
    "UsageRecord",
    "UsageStatus",
]

_EXPORTS = {
    "BudgetBalance": (".budget", "BudgetBalance"),
    "BudgetCaps": (".budget", "BudgetCaps"),
    "BudgetContext": (".budget", "BudgetContext"),
    "BudgetExceededError": (".budget", "BudgetExceededError"),
    "BudgetReservation": (".budget", "BudgetReservation"),
    "BudgetSettlement": (".budget", "BudgetSettlement"),
    "HourlyUsageRollup": (".metering", "HourlyUsageRollup"),
    "InMemoryBudgetLedger": (".budget", "InMemoryBudgetLedger"),
    "InMemoryMeteringLedger": (".metering", "InMemoryMeteringLedger"),
    "InMemoryModelCatalog": (".catalog", "InMemoryModelCatalog"),
    "InMemoryProviderHealthStore": (".routing", "InMemoryProviderHealthStore"),
    "MeteringExportRequest": (".metering", "MeteringExportRequest"),
    "ModelCatalogEntry": (".catalog", "ModelCatalogEntry"),
    "OrphanedReservationRelease": (".budget", "OrphanedReservationRelease"),
    "ProviderHealthSnapshot": (".routing", "ProviderHealthSnapshot"),
    "ProviderHealthState": (".routing", "ProviderHealthState"),
    "ProviderRoutingError": (".routing", "ProviderRoutingError"),
    "ProviderSelection": (".routing", "ProviderSelection"),
    "ReconciliationResult": (".metering", "ReconciliationResult"),
    "RoleModelAssignment": (".routing", "RoleModelAssignment"),
    "RoleTokenPolicy": (".catalog", "RoleTokenPolicy"),
    "RuleBasedProviderRouter": (".routing", "RuleBasedProviderRouter"),
    "TokenCap": (".catalog", "TokenCap"),
    "UsageRecord": (".metering", "UsageRecord"),
    "UsageStatus": (".metering", "UsageStatus"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name, __name__)
    return getattr(module, attr_name)
