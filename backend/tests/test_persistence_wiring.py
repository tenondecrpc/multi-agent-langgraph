from __future__ import annotations

import ast
from pathlib import Path

from backend.persistence import (
    PostgresBudgetLedger,
    PostgresControlPlaneStore,
    PostgresMeteringLedger,
    PostgresModelCatalog,
    PostgresRunRepository,
    RedisSharedProviderHealthStore,
    RedisWorkerController,
    SnapshotDrivenHandlerRegistry,
    build_persistence_adapters,
)
from backend.persistence.webhook import PostgresRedisWebhookGuard
from backend.worker import build_worker_bootstrap

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "backend" / "src" / "backend"
ALLOWED_DIRECT_CONSTRUCTION = {
    "persistence/factory.py",
}


def test_inmemory_adapters_are_not_constructed_directly_outside_factory_or_testing() -> None:
    violations: list[str] = []

    for path in SRC_ROOT.rglob("*.py"):
        relative = path.relative_to(SRC_ROOT).as_posix()
        if relative.startswith("persistence/testing/"):
            continue
        if relative in ALLOWED_DIRECT_CONSTRUCTION:
            continue

        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = _call_name(node.func)
                if callee.startswith("InMemory"):
                    violations.append(f"{relative}:{node.lineno}:{callee}")

    assert violations == []


def test_worker_bootstrap_resolves_controller_from_persistence_factory() -> None:
    bootstrap = build_worker_bootstrap()

    assert bootstrap.queue_name == "ticket-runs"
    assert hasattr(bootstrap.worker_controller, "begin_drain")


def test_persistence_factory_can_select_postgres_control_plane(
    monkeypatch,
) -> None:
    monkeypatch.setenv("BACKEND_CONTROL_PLANE_STORE_MODE", "postgres")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/postgres")
    monkeypatch.setenv("BACKEND_REDIS_URL", "redis://127.0.0.1:6379/0")

    adapters = build_persistence_adapters()

    assert isinstance(adapters.control_plane_store, PostgresControlPlaneStore)
    assert isinstance(adapters.handler_registry, SnapshotDrivenHandlerRegistry)


def test_persistence_factory_can_select_redis_worker_controller(monkeypatch) -> None:
    monkeypatch.setenv("BACKEND_WORKER_CONTROLLER_MODE", "redis")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/postgres")
    monkeypatch.setenv("BACKEND_REDIS_URL", "redis://127.0.0.1:6379/0")

    adapters = build_persistence_adapters()

    assert isinstance(adapters.worker_controller, RedisWorkerController)


def test_persistence_factory_can_select_postgres_budget_ledger(monkeypatch) -> None:
    monkeypatch.setenv("BACKEND_BUDGET_LEDGER_MODE", "postgres")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/postgres")
    monkeypatch.setenv("BACKEND_REDIS_URL", "redis://127.0.0.1:6379/0")

    adapters = build_persistence_adapters()

    assert isinstance(adapters.budget_ledger, PostgresBudgetLedger)


def test_persistence_factory_can_select_postgres_metering_ledger(monkeypatch) -> None:
    monkeypatch.setenv("BACKEND_METERING_LEDGER_MODE", "postgres")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/postgres")
    monkeypatch.setenv("BACKEND_REDIS_URL", "redis://127.0.0.1:6379/0")

    adapters = build_persistence_adapters()

    assert isinstance(adapters.metering_ledger, PostgresMeteringLedger)


def test_persistence_factory_can_select_postgres_model_catalog(monkeypatch) -> None:
    monkeypatch.setenv("BACKEND_MODEL_CATALOG_MODE", "postgres")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/postgres")
    monkeypatch.setenv("BACKEND_REDIS_URL", "redis://127.0.0.1:6379/0")

    adapters = build_persistence_adapters()

    assert isinstance(adapters.model_catalog, PostgresModelCatalog)


def test_persistence_factory_can_select_redis_provider_health_store(monkeypatch) -> None:
    monkeypatch.setenv("BACKEND_PROVIDER_HEALTH_STORE_MODE", "redis")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/postgres")
    monkeypatch.setenv("BACKEND_REDIS_URL", "redis://127.0.0.1:6379/0")

    adapters = build_persistence_adapters()

    assert isinstance(adapters.provider_health_store, RedisSharedProviderHealthStore)


def test_persistence_factory_forces_production_adapters_when_infrastructure_is_configured(
    monkeypatch,
) -> None:
    monkeypatch.setenv("BACKEND_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/postgres")
    monkeypatch.setenv("BACKEND_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("BACKEND_WEBHOOK_GUARD_MODE", "legacy")

    adapters = build_persistence_adapters()

    assert isinstance(adapters.run_repository, PostgresRunRepository)
    assert isinstance(adapters.control_plane_store, PostgresControlPlaneStore)
    assert isinstance(adapters.handler_registry, SnapshotDrivenHandlerRegistry)
    assert isinstance(adapters.worker_controller, RedisWorkerController)
    assert isinstance(adapters.budget_ledger, PostgresBudgetLedger)
    assert isinstance(adapters.metering_ledger, PostgresMeteringLedger)
    assert isinstance(adapters.model_catalog, PostgresModelCatalog)
    assert isinstance(adapters.provider_health_store, RedisSharedProviderHealthStore)
    assert isinstance(adapters.webhook_guard, PostgresRedisWebhookGuard)


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
