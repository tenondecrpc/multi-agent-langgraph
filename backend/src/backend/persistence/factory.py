from __future__ import annotations

import os
from dataclasses import dataclass, field

from backend.governance.catalog import ModelCatalogEntry, RoleTokenPolicy

from .contracts import (
    BudgetLedger,
    ControlPlaneStore,
    HandlerRegistry,
    MeteringLedger,
    ModelCatalog,
    ProviderHealthStore,
    RunRepository,
    WebhookGuard,
    WorkerController,
)
from .control_plane import (
    ControlPlaneSettings,
    build_control_plane_store,
    build_handler_registry,
    build_snapshot_activation_broadcaster,
)
from .db import DatabaseRuntime, build_database_runtime
from .encryption import EnvelopeCipher
from .governance import (
    DEPLOYMENT_PROFILE_ENV_KEY,
    BudgetLedgerSettings,
    MeteringLedgerSettings,
    ModelCatalogSettings,
    ProviderHealthSettings,
    build_budget_ledger,
    build_metering_ledger,
    build_model_catalog,
    build_provider_health_store,
)
from .health import PersistenceHealthService
from .redis import RedisRuntime, build_redis_runtime
from .runs import (
    PostgresCheckpointSaverHandle,
    RunRepositorySettings,
    build_checkpoint_saver_handle,
    build_run_repository,
)
from .telemetry import PersistenceTelemetry, bootstrap_telemetry
from .testing import InMemoryWebhookGuard
from .webhook import WebhookGuardSettings, build_webhook_guard
from .worker import WorkerControllerSettings, build_worker_controller


@dataclass(slots=True)
class PersistenceAdapters:
    run_repository: RunRepository
    control_plane_store: ControlPlaneStore
    handler_registry: HandlerRegistry
    worker_controller: WorkerController
    budget_ledger: BudgetLedger
    metering_ledger: MeteringLedger
    model_catalog: ModelCatalog
    provider_health_store: ProviderHealthStore
    webhook_guard: WebhookGuard
    database: DatabaseRuntime
    redis: RedisRuntime
    encryption: EnvelopeCipher
    health: PersistenceHealthService
    checkpoint_saver: PostgresCheckpointSaverHandle | None = None
    telemetry: PersistenceTelemetry = field(default_factory=bootstrap_telemetry)


def build_in_memory_persistence() -> PersistenceAdapters:
    from .testing import (
        InMemoryBudgetLedger,
        InMemoryControlPlaneStore,
        InMemoryHandlerRegistry,
        InMemoryMeteringLedger,
        InMemoryModelCatalog,
        InMemoryProviderHealthStore,
        InMemoryRunRepository,
        InMemoryWebhookGuard,
        InMemoryWorkerController,
    )

    database = build_database_runtime()
    redis = build_redis_runtime()
    encryption = EnvelopeCipher.from_env()
    health = PersistenceHealthService(
        database_ready=database.configured,
        redis_ready=redis.configured,
        encryption_ready=encryption.configured,
    )
    telemetry = bootstrap_telemetry()
    return PersistenceAdapters(
        run_repository=InMemoryRunRepository(),
        control_plane_store=InMemoryControlPlaneStore(),
        handler_registry=InMemoryHandlerRegistry(handler_refs=[]),
        worker_controller=InMemoryWorkerController(),
        budget_ledger=InMemoryBudgetLedger(),
        metering_ledger=InMemoryMeteringLedger(),
        model_catalog=InMemoryModelCatalog(
            entries=_default_model_catalog_entries(),
            role_token_policies=_default_role_token_policies(),
        ),
        provider_health_store=InMemoryProviderHealthStore(),
        webhook_guard=InMemoryWebhookGuard(secret="development-shared-secret"),
        database=database,
        redis=redis,
        encryption=encryption,
        health=health,
        telemetry=telemetry,
    )


def build_persistence_adapters() -> PersistenceAdapters:
    database = build_database_runtime()
    redis = build_redis_runtime()
    encryption = EnvelopeCipher.from_env()
    health = PersistenceHealthService(
        database_ready=database.configured,
        redis_ready=redis.configured,
        encryption_ready=encryption.configured,
    )
    telemetry = bootstrap_telemetry()
    if os.getenv(DEPLOYMENT_PROFILE_ENV_KEY) == "air_gapped":
        if not database.configured:
            raise RuntimeError(
                "air_gapped deployment requires PostgreSQL; in-memory dev fallback is disabled"
            )
        if not redis.configured:
            raise RuntimeError(
                "air_gapped deployment requires Redis; in-memory dev fallback is disabled"
            )
        if not encryption.configured:
            raise RuntimeError(
                "air_gapped deployment requires Vault-backed encryption; dev fallback is disabled"
            )
    if not database.configured:
        return build_in_memory_persistence()

    database_url = database.settings.sync_url()

    webhook_settings = WebhookGuardSettings.from_env()
    control_plane_settings = ControlPlaneSettings.from_env()
    worker_controller_settings = WorkerControllerSettings.from_env()
    budget_ledger_settings = BudgetLedgerSettings.from_env()
    metering_ledger_settings = MeteringLedgerSettings.from_env()
    model_catalog_settings = ModelCatalogSettings.from_env()
    provider_health_settings = ProviderHealthSettings.from_env()
    if database.configured:
        control_plane_settings = control_plane_settings.model_copy(update={"mode": "postgres"})
        metering_ledger_settings = metering_ledger_settings.model_copy(update={"mode": "postgres"})
        model_catalog_settings = model_catalog_settings.model_copy(update={"mode": "postgres"})
        run_repository_settings = RunRepositorySettings(mode="postgres")
    else:
        run_repository_settings = RunRepositorySettings.from_env()
    if database.configured and redis.settings.configured:
        worker_controller_settings = worker_controller_settings.model_copy(update={"mode": "redis"})
        budget_ledger_settings = budget_ledger_settings.model_copy(update={"mode": "postgres"})
        provider_health_settings = provider_health_settings.model_copy(update={"mode": "redis"})
        if webhook_settings.mode == "legacy":
            webhook_settings = webhook_settings.model_copy(update={"mode": "postgres_redis"})
    legacy_webhook_guard = None
    if webhook_settings.mode in {"legacy", "shadow"}:
        legacy_webhook_guard = InMemoryWebhookGuard(
            secret=webhook_settings.secret,
            freshness_window_seconds=webhook_settings.freshness_window_seconds,
            per_minute_limit=webhook_settings.per_minute_limit,
        )
    snapshot_broadcaster = None
    if control_plane_settings.mode == "postgres":
        if not redis.settings.configured:
            raise RuntimeError(
                "BACKEND_CONTROL_PLANE_STORE_MODE=postgres requires a configured Redis URL"
            )
        snapshot_broadcaster = build_snapshot_activation_broadcaster(redis.settings)

    checkpoint_saver = build_checkpoint_saver_handle(database_url)
    run_repository = build_run_repository(
        database_url=database_url,
        legacy_repository=None,
        settings=run_repository_settings,
        checkpoint_saver=checkpoint_saver,
        telemetry=telemetry,
    )

    return PersistenceAdapters(
        run_repository=run_repository,
        control_plane_store=build_control_plane_store(
            database_url=database_url,
            legacy_store=None,
            broadcaster=snapshot_broadcaster,
            settings=control_plane_settings,
            telemetry=telemetry,
        ),
        handler_registry=build_handler_registry(
            database_url=database_url,
            legacy_registry=None,
            broadcaster=snapshot_broadcaster,
            settings=control_plane_settings,
            telemetry=telemetry,
        ),
        worker_controller=build_worker_controller(
            database_url=database_url,
            redis_settings=redis.settings,
            legacy_controller=None,
            settings=worker_controller_settings,
            telemetry=telemetry,
        ),
        budget_ledger=build_budget_ledger(
            database_url=database_url,
            redis_settings=redis.settings,
            legacy_ledger=None,
            settings=budget_ledger_settings,
            telemetry=telemetry,
        ),
        metering_ledger=build_metering_ledger(
            database_url=database_url,
            legacy_ledger=None,
            settings=metering_ledger_settings,
            telemetry=telemetry,
        ),
        model_catalog=build_model_catalog(
            database_url=database_url,
            settings=model_catalog_settings,
            telemetry=telemetry,
        ),
        provider_health_store=build_provider_health_store(
            database_url=database_url,
            redis_settings=redis.settings,
            settings=provider_health_settings,
            telemetry=telemetry,
        ),
        webhook_guard=build_webhook_guard(
            legacy_guard=legacy_webhook_guard,
            database_url=database_url,
            redis_settings=redis.settings,
            settings=webhook_settings,
            telemetry=telemetry,
        ),
        database=database,
        redis=redis,
        encryption=encryption,
        health=health,
        checkpoint_saver=checkpoint_saver,
        telemetry=telemetry,
    )


def _default_model_catalog_entries() -> list[ModelCatalogEntry]:
    return [
        ModelCatalogEntry(
            model_id="gpt-4.1",
            provider_id="openai",
            deployment_profile="connected",
            max_input_tokens=128_000,
            max_output_tokens=16_000,
            default_price_card_id="card-openai-v1",
            supports_tools=True,
            supports_json_mode=True,
            supports_streaming=True,
            allowed_fallback_targets=["llama3.1"],
        ),
        ModelCatalogEntry(
            model_id="llama3.1",
            provider_id="ollama",
            deployment_profile="connected",
            max_input_tokens=32_000,
            max_output_tokens=8_000,
            default_price_card_id="card-ollama-v1",
            supports_tools=True,
            supports_json_mode=True,
            supports_streaming=False,
        ),
        ModelCatalogEntry(
            model_id="opencode-go/kimi-k2.5",
            provider_id="opencode-go",
            deployment_profile="air_gapped",
            max_input_tokens=16_000,
            max_output_tokens=4_000,
            default_price_card_id="card-airgap-v1",
            supports_tools=True,
            supports_json_mode=True,
            supports_streaming=False,
            allowed_fallback_targets=["opencode-go/minimax-m2.7"],
        ),
        ModelCatalogEntry(
            model_id="opencode-go/minimax-m2.7",
            provider_id="opencode-go",
            deployment_profile="air_gapped",
            max_input_tokens=16_000,
            max_output_tokens=4_000,
            default_price_card_id="card-airgap-v1",
            supports_tools=True,
            supports_json_mode=True,
            supports_streaming=False,
        ),
    ]


def _default_role_token_policies() -> list[RoleTokenPolicy]:
    return [
        RoleTokenPolicy(role="planner", max_input_tokens=8_000, max_output_tokens=2_000),
        RoleTokenPolicy(role="coder", max_input_tokens=12_000, max_output_tokens=4_000),
        RoleTokenPolicy(role="tester", max_input_tokens=12_000, max_output_tokens=4_000),
        RoleTokenPolicy(role="reviewer", max_input_tokens=10_000, max_output_tokens=3_000),
        RoleTokenPolicy(role="pr_creator", max_input_tokens=6_000, max_output_tokens=2_000),
    ]
