from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from importlib.resources import files
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import Connection, Engine, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.governance.budget import BudgetBalance, BudgetCaps, BudgetContext, BudgetExceededError, BudgetReservation
from backend.governance.metering import (
    HourlyUsageRollup,
    MeteringExportRequest,
    ReconciliationResult,
    UsageRecord,
)
from backend.governance.routing import ProviderHealthSnapshot, ProviderHealthState

from .contracts import BudgetLedger, MeteringLedger
from .db import ALL_TEAMS_SCOPE, tenant_guc_values
from .redis import RedisSettings, build_redis_client
from .schema import (
    audit_events,
    budget_cap_snapshots,
    budget_charges,
    budget_denials,
    budget_reservations,
    metering_facts,
    metering_hourly_rollups,
    model_catalog_entries,
    provider_health_events,
    role_token_policies,
)
from .telemetry import PersistenceTelemetry, bootstrap_telemetry

BUDGET_LEDGER_MODE_ENV_KEY = "BACKEND_BUDGET_LEDGER_MODE"
METERING_LEDGER_MODE_ENV_KEY = "BACKEND_METERING_LEDGER_MODE"
MODEL_CATALOG_MODE_ENV_KEY = "BACKEND_MODEL_CATALOG_MODE"
PROVIDER_HEALTH_STORE_MODE_ENV_KEY = "BACKEND_PROVIDER_HEALTH_STORE_MODE"
DEPLOYMENT_PROFILE_ENV_KEY = "BACKEND_DEPLOYMENT_PROFILE"
MODEL_CATALOG_BUNDLE_PATH_ENV_KEY = "BACKEND_MODEL_CATALOG_BUNDLE_PATH"
PROVIDER_FAILURE_THRESHOLD_ENV_KEY = "BACKEND_PROVIDER_FAILURE_THRESHOLD"
PROVIDER_RECOVERY_PROBE_LIMIT_ENV_KEY = "BACKEND_PROVIDER_RECOVERY_PROBE_LIMIT"
_RESERVATION_SCRIPT = """
local ticket = redis.call('GET', KEYS[1])
local daily = redis.call('GET', KEYS[2])
local monthly = redis.call('GET', KEYS[3])
if not ticket or not daily or not monthly then
  return {-1, -1, -1, -1}
end
local amount = tonumber(ARGV[1])
ticket = tonumber(ticket)
daily = tonumber(daily)
monthly = tonumber(monthly)
if ticket < amount or daily < amount or monthly < amount then
  return {0, ticket, daily, monthly}
end
ticket = redis.call('DECRBY', KEYS[1], amount)
daily = redis.call('DECRBY', KEYS[2], amount)
monthly = redis.call('DECRBY', KEYS[3], amount)
return {1, ticket, daily, monthly}
"""
_PROVIDER_FAILURE_SCRIPT = """
local threshold = tonumber(ARGV[1])
local state = redis.call('HGET', KEYS[1], 'state') or 'closed'
local failures = tonumber(redis.call('HGET', KEYS[1], 'consecutive_failures') or '0') + 1
local probes = tonumber(redis.call('HGET', KEYS[1], 'remaining_probe_attempts') or '0')
if failures >= threshold then
  state = 'open'
  probes = 0
end
redis.call('HSET', KEYS[1], 'state', state, 'consecutive_failures', failures, 'remaining_probe_attempts', probes)
redis.call('EXPIRE', KEYS[1], 86400)
return {state, failures, probes}
"""
_PROVIDER_SUCCESS_SCRIPT = """
redis.call('HSET', KEYS[1], 'state', 'closed', 'consecutive_failures', 0, 'remaining_probe_attempts', 0)
redis.call('EXPIRE', KEYS[1], 86400)
return {'closed', 0, 0}
"""
_PROVIDER_HALF_OPEN_SCRIPT = """
local probes = tonumber(ARGV[1])
redis.call('HSET', KEYS[1], 'state', 'half_open', 'remaining_probe_attempts', probes)
redis.call('EXPIRE', KEYS[1], 86400)
local failures = tonumber(redis.call('HGET', KEYS[1], 'consecutive_failures') or '0')
return {'half_open', failures, probes}
"""
_PROVIDER_ALLOW_REQUEST_SCRIPT = """
local state = redis.call('HGET', KEYS[1], 'state') or 'closed'
local failures = tonumber(redis.call('HGET', KEYS[1], 'consecutive_failures') or '0')
local probes = tonumber(redis.call('HGET', KEYS[1], 'remaining_probe_attempts') or '0')
if state == 'open' then
  return {0, state, failures, probes}
end
if state == 'half_open' then
  if probes <= 0 then
    return {0, state, failures, probes}
  end
  probes = redis.call('HINCRBY', KEYS[1], 'remaining_probe_attempts', -1)
  return {1, state, failures, probes}
end
return {1, state, failures, probes}
"""


class RedisBudgetLike(Protocol):
    def eval(self, script: str, numkeys: int, *keys_and_args): ...

    def get(self, key: str) -> str | None: ...

    def incrby(self, key: str, amount: int = 1) -> int: ...

    def set(self, key: str, value: str, nx: bool = False) -> bool | None: ...


class BudgetLedgerSettings(BaseModel):
    mode: Literal["legacy", "postgres"] = "legacy"

    @classmethod
    def from_env(cls) -> BudgetLedgerSettings:
        mode = os.getenv(BUDGET_LEDGER_MODE_ENV_KEY, "legacy")
        if mode not in {"legacy", "postgres"}:
            raise ValueError(
                f"{BUDGET_LEDGER_MODE_ENV_KEY} must be 'legacy' or 'postgres', got '{mode}'"
            )
        return cls(mode=mode)  # type: ignore[arg-type]


class MeteringLedgerSettings(BaseModel):
    mode: Literal["legacy", "postgres"] = "legacy"

    @classmethod
    def from_env(cls) -> MeteringLedgerSettings:
        mode = os.getenv(METERING_LEDGER_MODE_ENV_KEY, "legacy")
        if mode not in {"legacy", "postgres"}:
            raise ValueError(
                f"{METERING_LEDGER_MODE_ENV_KEY} must be 'legacy' or 'postgres', got '{mode}'"
            )
        return cls(mode=mode)  # type: ignore[arg-type]


class ModelCatalogSettings(BaseModel):
    mode: Literal["legacy", "postgres"] = "legacy"
    deployment_profile: Literal["connected", "air_gapped"] = "connected"
    bundle_path: str | None = None

    @classmethod
    def from_env(cls) -> ModelCatalogSettings:
        mode = os.getenv(MODEL_CATALOG_MODE_ENV_KEY, "legacy")
        if mode not in {"legacy", "postgres"}:
            raise ValueError(
                f"{MODEL_CATALOG_MODE_ENV_KEY} must be 'legacy' or 'postgres', got '{mode}'"
            )
        deployment_profile = os.getenv(DEPLOYMENT_PROFILE_ENV_KEY, "connected")
        if deployment_profile not in {"connected", "air_gapped"}:
            raise ValueError(
                f"{DEPLOYMENT_PROFILE_ENV_KEY} must be 'connected' or 'air_gapped', got "
                f"'{deployment_profile}'"
            )
        return cls(
            mode=mode,  # type: ignore[arg-type]
            deployment_profile=deployment_profile,  # type: ignore[arg-type]
            bundle_path=os.getenv(MODEL_CATALOG_BUNDLE_PATH_ENV_KEY),
        )


class ProviderHealthSettings(BaseModel):
    mode: Literal["legacy", "redis"] = "legacy"
    deployment_profile: Literal["connected", "air_gapped"] = "connected"
    failure_threshold: int = 2
    recovery_probe_limit: int = 1

    @property
    def fail_closed_without_redis(self) -> bool:
        return self.deployment_profile == "air_gapped"

    @classmethod
    def from_env(cls) -> ProviderHealthSettings:
        mode = os.getenv(PROVIDER_HEALTH_STORE_MODE_ENV_KEY, "legacy")
        if mode not in {"legacy", "redis"}:
            raise ValueError(
                f"{PROVIDER_HEALTH_STORE_MODE_ENV_KEY} must be 'legacy' or 'redis', got '{mode}'"
            )
        deployment_profile = os.getenv(DEPLOYMENT_PROFILE_ENV_KEY, "connected")
        if deployment_profile not in {"connected", "air_gapped"}:
            raise ValueError(
                f"{DEPLOYMENT_PROFILE_ENV_KEY} must be 'connected' or 'air_gapped', got "
                f"'{deployment_profile}'"
            )
        return cls(
            mode=mode,  # type: ignore[arg-type]
            deployment_profile=deployment_profile,  # type: ignore[arg-type]
            failure_threshold=int(os.getenv(PROVIDER_FAILURE_THRESHOLD_ENV_KEY, "2")),
            recovery_probe_limit=int(os.getenv(PROVIDER_RECOVERY_PROBE_LIMIT_ENV_KEY, "1")),
        )


class PostgresBudgetLedger:
    def __init__(
        self,
        database_url: str,
        *,
        redis_settings: RedisSettings | None = None,
        redis_client: RedisBudgetLike | None = None,
        engine: Engine | None = None,
        logger: logging.Logger | None = None,
        now_provider=None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self._engine = engine or create_engine(database_url, future=True, pool_pre_ping=True)
        self._redis = redis_client or build_redis_client(redis_settings or RedisSettings.from_env())
        self._logger = logger or logging.getLogger(__name__)
        self._now = now_provider or (lambda: datetime.now(tz=UTC))
        self._telemetry = telemetry or bootstrap_telemetry()

    def configure_caps(self, context: BudgetContext, caps: BudgetCaps) -> None:
        with self._telemetry.trace(
            "budget_configure_caps",
            subsystem="budget_ledger",
            operation="configure_caps",
            tenant_id=context.tenant_id,
            team_id=context.team_id,
            run_id=context.run_id,
        ):
            stmt = pg_insert(budget_cap_snapshots).values(
                tenant_id=context.tenant_id,
                team_id=context.team_id,
                run_id=context.run_id,
                ticket_key=context.ticket_key,
                role=context.role,
                ticket_cap_usd=caps.ticket_cap_usd,
                daily_team_cap_usd=caps.daily_team_cap_usd,
                monthly_team_cap_usd=caps.monthly_team_cap_usd,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[budget_cap_snapshots.c.run_id],
                set_={
                    "tenant_id": stmt.excluded.tenant_id,
                    "team_id": stmt.excluded.team_id,
                    "ticket_key": stmt.excluded.ticket_key,
                    "role": stmt.excluded.role,
                    "ticket_cap_usd": stmt.excluded.ticket_cap_usd,
                    "daily_team_cap_usd": stmt.excluded.daily_team_cap_usd,
                    "monthly_team_cap_usd": stmt.excluded.monthly_team_cap_usd,
                    "updated_at": text("now()"),
                },
            )
            with self._scoped_transaction(context.tenant_id, context.team_id) as connection:
                connection.execute(stmt)
        self.reconcile(context)

    def reserve(self, context: BudgetContext, worst_case_cost_usd: Decimal) -> BudgetReservation:
        with self._telemetry.trace(
            "budget_reserve",
            subsystem="budget_ledger",
            operation="reserve",
            tenant_id=context.tenant_id,
            team_id=context.team_id,
            run_id=context.run_id,
        ):
            caps = self._load_caps(context)
            self._ensure_counters(context)
            reservation_id = str(uuid4())
            cents = _usd_to_cents(worst_case_cost_usd)
            success, ticket_remaining, daily_remaining, monthly_remaining = self._reserve_cents(
                context,
                cents,
            )
            if success != 1:
                self._telemetry.increment(
                    "devsquad_budget_reservation_denials_total",
                    tenant_id=context.tenant_id,
                    team_id=context.team_id,
                )
                with self._scoped_transaction(context.tenant_id, context.team_id) as connection:
                    connection.execute(
                        budget_denials.insert().values(
                            tenant_id=context.tenant_id,
                            team_id=context.team_id,
                            run_id=context.run_id,
                            ticket_key=context.ticket_key,
                            role=context.role,
                            requested_amount_usd=worst_case_cost_usd,
                            ticket_cap_usd=caps.ticket_cap_usd,
                            daily_team_cap_usd=caps.daily_team_cap_usd,
                            monthly_team_cap_usd=caps.monthly_team_cap_usd,
                            denial_reason="budget_exhausted",
                            evidence_summary=(
                                "ticket_remaining="
                                f"{_cents_to_usd(ticket_remaining)}, "
                                "daily_remaining="
                                f"{_cents_to_usd(daily_remaining)}, "
                                "monthly_remaining="
                                f"{_cents_to_usd(monthly_remaining)}"
                            ),
                        )
                    )
                raise BudgetExceededError()

            try:
                with self._scoped_transaction(context.tenant_id, context.team_id) as connection:
                    connection.execute(
                        budget_reservations.insert().values(
                            reservation_id=reservation_id,
                            tenant_id=context.tenant_id,
                            team_id=context.team_id,
                            run_id=context.run_id,
                            ticket_key=context.ticket_key,
                            role=context.role,
                            reserved_amount_usd=worst_case_cost_usd,
                            ticket_cap_usd=caps.ticket_cap_usd,
                            daily_team_cap_usd=caps.daily_team_cap_usd,
                            monthly_team_cap_usd=caps.monthly_team_cap_usd,
                            ticket_cap_remaining_usd=_cents_to_usd(ticket_remaining),
                            daily_team_cap_remaining_usd=_cents_to_usd(daily_remaining),
                            monthly_team_cap_remaining_usd=_cents_to_usd(monthly_remaining),
                            status="active",
                        )
                    )
            except Exception:
                self._credit_counters(context, cents)
                raise

            return BudgetReservation(
                reservation_id=reservation_id,
                reserved_amount_usd=worst_case_cost_usd,
                ticket_cap_remaining_usd=_cents_to_usd(ticket_remaining),
                daily_team_cap_remaining_usd=_cents_to_usd(daily_remaining),
                monthly_team_cap_remaining_usd=_cents_to_usd(monthly_remaining),
            )

    def settle(self, reservation_id: str, actual_cost_usd: Decimal) -> None:
        with self._telemetry.trace(
            "budget_settle",
            subsystem="budget_ledger",
            operation="settle",
        ):
            with self._engine.begin() as connection:
                row = connection.execute(
                    select(budget_reservations).where(
                        budget_reservations.c.reservation_id == reservation_id
                    )
                ).mappings().first()
                if row is None:
                    raise KeyError(f"Unknown reservation `{reservation_id}`.")
                if row["status"] != "active":
                    raise ValueError(f"Reservation `{reservation_id}` is not active.")

                reserved_amount = Decimal(row["reserved_amount_usd"])
                if actual_cost_usd > reserved_amount:
                    raise ValueError("Actual cost exceeded the reserved worst-case estimate.")

                refunded_amount = reserved_amount - actual_cost_usd
                connection.execute(
                    budget_charges.insert().values(
                        reservation_id=reservation_id,
                        tenant_id=row["tenant_id"],
                        team_id=row["team_id"],
                        run_id=row["run_id"],
                        estimated_cost_usd=reserved_amount,
                        actual_cost_usd=actual_cost_usd,
                        refunded_amount_usd=refunded_amount,
                    )
                )
                connection.execute(
                    budget_reservations.update()
                    .where(budget_reservations.c.reservation_id == reservation_id)
                    .values(
                        status="settled",
                        release_reason="settled",
                        released_amount_usd=refunded_amount,
                        updated_at=text("now()"),
                    )
                )
                context = BudgetContext(
                    tenant_id=row["tenant_id"],
                    team_id=row["team_id"],
                    run_id=row["run_id"],
                    ticket_key=row["ticket_key"],
                    role=row["role"],
                )

            if refunded_amount > 0:
                self._credit_counters(context, _usd_to_cents(refunded_amount))

    def release_orphaned(self, reservation_id: str, reason: str) -> None:
        with self._telemetry.trace(
            "budget_release_orphaned",
            subsystem="budget_ledger",
            operation="release_orphaned",
        ):
            with self._engine.begin() as connection:
                row = connection.execute(
                    select(budget_reservations).where(
                        budget_reservations.c.reservation_id == reservation_id
                    )
                ).mappings().first()
                if row is None:
                    raise KeyError(f"Unknown reservation `{reservation_id}`.")
                if row["status"] != "active":
                    raise ValueError(f"Reservation `{reservation_id}` is not active.")

                reserved_amount = Decimal(row["reserved_amount_usd"])
                connection.execute(
                    budget_reservations.update()
                    .where(budget_reservations.c.reservation_id == reservation_id)
                    .values(
                        status="released",
                        release_reason=reason,
                        released_amount_usd=reserved_amount,
                        updated_at=text("now()"),
                    )
                )
                context = BudgetContext(
                    tenant_id=row["tenant_id"],
                    team_id=row["team_id"],
                    run_id=row["run_id"],
                    ticket_key=row["ticket_key"],
                    role=row["role"],
                )

            self._credit_counters(context, _usd_to_cents(reserved_amount))

    def balance(self, context: BudgetContext) -> BudgetBalance:
        with self._telemetry.trace(
            "budget_balance",
            subsystem="budget_ledger",
            operation="balance",
            tenant_id=context.tenant_id,
            team_id=context.team_id,
            run_id=context.run_id,
        ):
            caps = self._load_caps(context)
            self._ensure_counters(context)
            remaining = self._remaining_from_postgres(context, caps)
            return BudgetBalance(
                ticket_remaining_usd=remaining["ticket_remaining_usd"],
                daily_team_remaining_usd=remaining["daily_team_remaining_usd"],
                monthly_team_remaining_usd=remaining["monthly_team_remaining_usd"],
            )

    def reconcile(self, context: BudgetContext) -> BudgetBalance:
        caps = self._load_caps(context)
        remaining = self._remaining_from_postgres(context, caps)
        ticket_key, daily_key, monthly_key = _counter_keys(context, self._now())
        self._redis.set(ticket_key, str(_usd_to_cents(remaining["ticket_remaining_usd"])))
        self._redis.set(daily_key, str(_usd_to_cents(remaining["daily_team_remaining_usd"])))
        self._redis.set(monthly_key, str(_usd_to_cents(remaining["monthly_team_remaining_usd"])))
        return BudgetBalance(
            ticket_remaining_usd=remaining["ticket_remaining_usd"],
            daily_team_remaining_usd=remaining["daily_team_remaining_usd"],
            monthly_team_remaining_usd=remaining["monthly_team_remaining_usd"],
        )

    def _load_caps(self, context: BudgetContext) -> BudgetCaps:
        with self._scoped_transaction(context.tenant_id, context.team_id) as connection:
            row = connection.execute(
                select(budget_cap_snapshots).where(
                    budget_cap_snapshots.c.run_id == context.run_id
                )
            ).mappings().first()
        if row is None:
            raise ValueError(f"Budget caps were not configured for run `{context.run_id}`.")
        return BudgetCaps(
            ticket_cap_usd=Decimal(row["ticket_cap_usd"]),
            daily_team_cap_usd=Decimal(row["daily_team_cap_usd"]),
            monthly_team_cap_usd=Decimal(row["monthly_team_cap_usd"]),
        )

    def _ensure_counters(self, context: BudgetContext) -> None:
        keys = _counter_keys(context, self._now())
        if any(self._redis.get(key) is None for key in keys):
            self.reconcile(context)

    def _reserve_cents(self, context: BudgetContext, cents: int) -> tuple[int, int, int, int]:
        redis_result = self._redis.eval(
            _RESERVATION_SCRIPT,
            3,
            *_counter_keys(context, self._now()),
            cents,
        )
        success, ticket_remaining, daily_remaining, monthly_remaining = [int(v) for v in redis_result]
        if success == -1:
            self.reconcile(context)
            redis_result = self._redis.eval(
                _RESERVATION_SCRIPT,
                3,
                *_counter_keys(context, self._now()),
                cents,
            )
            success, ticket_remaining, daily_remaining, monthly_remaining = [
                int(v) for v in redis_result
            ]
        return success, ticket_remaining, daily_remaining, monthly_remaining

    def _remaining_from_postgres(
        self,
        context: BudgetContext,
        caps: BudgetCaps,
    ) -> dict[str, Decimal]:
        now = self._now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        with self._scoped_transaction(context.tenant_id, context.team_id) as connection:
            ticket_active = connection.execute(
                text(
                    """
                    SELECT COALESCE(SUM(reserved_amount_usd), 0)
                    FROM budget_reservations
                    WHERE run_id = :run_id
                      AND status = 'active'
                    """
                ),
                {"run_id": context.run_id},
            ).scalar_one()
            ticket_actual = connection.execute(
                text(
                    """
                    SELECT COALESCE(SUM(actual_cost_usd), 0)
                    FROM budget_charges
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": context.run_id},
            ).scalar_one()
            team_active_daily = connection.execute(
                text(
                    """
                    SELECT COALESCE(SUM(reserved_amount_usd), 0)
                    FROM budget_reservations
                    WHERE tenant_id = :tenant_id
                      AND team_id = :team_id
                      AND status = 'active'
                      AND created_at >= :day_start
                    """
                ),
                {
                    "tenant_id": context.tenant_id,
                    "team_id": context.team_id,
                    "day_start": day_start,
                },
            ).scalar_one()
            team_actual_daily = connection.execute(
                text(
                    """
                    SELECT COALESCE(SUM(actual_cost_usd), 0)
                    FROM budget_charges
                    WHERE tenant_id = :tenant_id
                      AND team_id = :team_id
                      AND created_at >= :day_start
                    """
                ),
                {
                    "tenant_id": context.tenant_id,
                    "team_id": context.team_id,
                    "day_start": day_start,
                },
            ).scalar_one()
            team_active_monthly = connection.execute(
                text(
                    """
                    SELECT COALESCE(SUM(reserved_amount_usd), 0)
                    FROM budget_reservations
                    WHERE tenant_id = :tenant_id
                      AND team_id = :team_id
                      AND status = 'active'
                      AND created_at >= :month_start
                    """
                ),
                {
                    "tenant_id": context.tenant_id,
                    "team_id": context.team_id,
                    "month_start": month_start,
                },
            ).scalar_one()
            team_actual_monthly = connection.execute(
                text(
                    """
                    SELECT COALESCE(SUM(actual_cost_usd), 0)
                    FROM budget_charges
                    WHERE tenant_id = :tenant_id
                      AND team_id = :team_id
                      AND created_at >= :month_start
                    """
                ),
                {
                    "tenant_id": context.tenant_id,
                    "team_id": context.team_id,
                    "month_start": month_start,
                },
            ).scalar_one()

        return {
            "ticket_remaining_usd": max(
                Decimal("0"),
                caps.ticket_cap_usd - Decimal(ticket_active) - Decimal(ticket_actual),
            ),
            "daily_team_remaining_usd": max(
                Decimal("0"),
                caps.daily_team_cap_usd
                - Decimal(team_active_daily)
                - Decimal(team_actual_daily),
            ),
            "monthly_team_remaining_usd": max(
                Decimal("0"),
                caps.monthly_team_cap_usd
                - Decimal(team_active_monthly)
                - Decimal(team_actual_monthly),
            ),
        }

    @contextmanager
    def _scoped_transaction(self, tenant_id: str, team_id: str) -> Iterator[Connection]:
        with self._engine.begin() as connection:
            for key, value in tenant_guc_values(tenant_id=tenant_id, team_id=team_id).items():
                connection.execute(
                    text("SELECT set_config(:key, :value, true)"),
                    {"key": key, "value": value},
                )
            yield connection

    def _credit_counters(self, context: BudgetContext, cents: int) -> None:
        if cents <= 0:
            return
        ticket_key, daily_key, monthly_key = _counter_keys(context, self._now())
        try:
            self._redis.incrby(ticket_key, cents)
            self._redis.incrby(daily_key, cents)
            self._redis.incrby(monthly_key, cents)
        except Exception:
            self._logger.warning(
                "budget_counter_credit_failed",
                extra={
                    "tenant_id": context.tenant_id,
                    "team_id": context.team_id,
                    "run_id": context.run_id,
                    "cents": cents,
                    "subsystem": "budget_ledger",
                },
            )


def build_budget_ledger(
    *,
    database_url: str | None,
    redis_settings: RedisSettings,
    legacy_ledger: BudgetLedger | None,
    settings: BudgetLedgerSettings | None = None,
    logger: logging.Logger | None = None,
    telemetry: PersistenceTelemetry | None = None,
) -> BudgetLedger:
    resolved = settings or BudgetLedgerSettings.from_env()
    if resolved.mode == "legacy":
        if legacy_ledger is None:
            raise RuntimeError("Legacy budget-ledger mode requires an in-memory test double.")
        return legacy_ledger
    if not database_url:
        raise RuntimeError(
            f"{BUDGET_LEDGER_MODE_ENV_KEY}=postgres requires a configured database URL"
        )
    if not redis_settings.configured:
        raise RuntimeError(
            f"{BUDGET_LEDGER_MODE_ENV_KEY}=postgres requires a configured Redis URL"
        )
    return PostgresBudgetLedger(
        database_url,
        redis_settings=redis_settings,
        logger=logger,
        telemetry=telemetry,
    )


class PostgresMeteringLedger:
    def __init__(
        self,
        database_url: str,
        *,
        engine: Engine | None = None,
        logger: logging.Logger | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self._engine = engine or create_engine(database_url, future=True, pool_pre_ping=True)
        self._logger = logger or logging.getLogger(__name__)
        self._telemetry = telemetry or bootstrap_telemetry()

    def record_usage(self, record: UsageRecord) -> None:
        with self._telemetry.trace(
            "metering_record_usage",
            subsystem="metering_ledger",
            operation="record_usage",
            tenant_id=record.tenant_id,
            team_id=record.team_id,
            run_id=record.run_id,
        ):
            with self._scoped_transaction(record.tenant_id, record.team_id) as connection:
                connection.execute(
                    pg_insert(metering_facts).values(
                        usage_id=record.usage_id,
                        tenant_id=record.tenant_id,
                        team_id=record.team_id,
                        run_id=record.run_id,
                        ticket_key=record.ticket_key,
                        role=record.role,
                        provider_id=record.provider_id,
                        model_id=record.model_id,
                        deployment_profile=record.deployment_profile,
                        fallback_used=record.fallback_used,
                        input_tokens=record.input_tokens,
                        output_tokens=record.output_tokens,
                        cached_tokens=record.cached_tokens,
                        latency_ms=record.latency_ms,
                        request_count=record.request_count,
                        reservation_id=record.reservation_id,
                        estimated_cost_usd=record.estimated_cost_usd,
                        actual_cost_usd=record.actual_cost_usd,
                        rate_card_id=record.rate_card_id,
                        trace_id=record.trace_id,
                        span_id=record.span_id,
                        started_at=record.started_at,
                        completed_at=record.completed_at,
                        status=record.status,
                    )
                )

    def build_hourly_rollups(
        self,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> list[HourlyUsageRollup]:
        facts = self._facts_for_period(tenant_id=tenant_id, period_start=period_start, period_end=period_end)
        groups: dict[tuple[datetime, str, str, str, str, str, str], HourlyUsageRollup] = {}
        for fact in facts:
            bucket_start = fact.completed_at.replace(minute=0, second=0, microsecond=0)
            key = (
                bucket_start,
                fact.tenant_id,
                fact.team_id,
                fact.role,
                fact.provider_id,
                fact.model_id,
                fact.rate_card_id,
            )
            if key not in groups:
                groups[key] = HourlyUsageRollup(
                    rollup_id=(
                        f"{bucket_start.isoformat()}:{fact.team_id}:{fact.role}:"
                        f"{fact.provider_id}:{fact.model_id}:{fact.rate_card_id}"
                    ),
                    bucket_start=bucket_start,
                    tenant_id=fact.tenant_id,
                    team_id=fact.team_id,
                    role=fact.role,
                    provider_id=fact.provider_id,
                    model_id=fact.model_id,
                    rate_card_id=fact.rate_card_id,
                    request_count=0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_actual_cost_usd=Decimal("0"),
                )

            rollup = groups[key]
            rollup.request_count += fact.request_count
            rollup.total_input_tokens += fact.input_tokens
            rollup.total_output_tokens += fact.output_tokens
            rollup.total_actual_cost_usd += fact.actual_cost_usd
            rollup.usage_ids.append(fact.usage_id)

        if not groups:
            return []

        scope_team_id = facts[0].team_id
        with self._scoped_transaction(tenant_id, scope_team_id) as connection:
            for rollup in groups.values():
                stmt = pg_insert(metering_hourly_rollups).values(
                    rollup_id=rollup.rollup_id,
                    bucket_start=rollup.bucket_start,
                    tenant_id=rollup.tenant_id,
                    team_id=rollup.team_id,
                    role=rollup.role,
                    provider_id=rollup.provider_id,
                    model_id=rollup.model_id,
                    rate_card_id=rollup.rate_card_id,
                    request_count=rollup.request_count,
                    total_input_tokens=rollup.total_input_tokens,
                    total_output_tokens=rollup.total_output_tokens,
                    total_actual_cost_usd=rollup.total_actual_cost_usd,
                    usage_ids=rollup.usage_ids,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[metering_hourly_rollups.c.rollup_id],
                    set_={
                        "request_count": stmt.excluded.request_count,
                        "total_input_tokens": stmt.excluded.total_input_tokens,
                        "total_output_tokens": stmt.excluded.total_output_tokens,
                        "total_actual_cost_usd": stmt.excluded.total_actual_cost_usd,
                        "usage_ids": stmt.excluded.usage_ids,
                        "updated_at": text("now()"),
                    },
                )
                connection.execute(stmt)

        return list(groups.values())

    def export(self, request: MeteringExportRequest) -> str:
        if request.format == "csv":
            return self._export_rollups_csv(request)
        if request.format == "jsonl":
            if request.schema_version == "v2":
                import json

                return "\n".join(
                    json.dumps(
                        {
                            "schema_version": "v2",
                            "usage": fact.model_dump(mode="json"),
                        }
                    )
                    for fact in self._facts_for_period(
                        tenant_id=request.tenant_id,
                        period_start=request.period_start,
                        period_end=request.period_end,
                    )
                )
            return "\n".join(
                fact.model_dump_json()
                for fact in self._facts_for_period(
                    tenant_id=request.tenant_id,
                    period_start=request.period_start,
                    period_end=request.period_end,
                )
            )
        raise ValueError(f"Unsupported export format `{request.format}`.")

    def reconcile(
        self,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
        provider_reported_total_usd: Decimal,
    ) -> ReconciliationResult:
        facts = self._facts_for_period(tenant_id=tenant_id, period_start=period_start, period_end=period_end)
        rollups = self.build_hourly_rollups(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
        )
        metered_total = sum((fact.actual_cost_usd for fact in facts), start=Decimal("0"))
        return ReconciliationResult(
            period_start=period_start,
            period_end=period_end,
            metered_total_usd=metered_total,
            provider_reported_total_usd=provider_reported_total_usd,
            drift_amount_usd=provider_reported_total_usd - metered_total,
            usage_ids=[fact.usage_id for fact in facts],
            rollup_ids=[rollup.rollup_id for rollup in rollups],
        )

    def _facts_for_period(
        self,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> list[UsageRecord]:
        with self._scoped_transaction(tenant_id, ALL_TEAMS_SCOPE) as connection:
            rows = connection.execute(
                select(metering_facts)
                .where(metering_facts.c.tenant_id == tenant_id)
                .where(metering_facts.c.completed_at >= period_start)
                .where(metering_facts.c.completed_at <= period_end)
                .order_by(metering_facts.c.completed_at.asc())
            ).mappings().all()
        return [UsageRecord.model_validate(row) for row in rows]

    def _rollups_for_period(
        self,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> list[HourlyUsageRollup]:
        with self._scoped_transaction(tenant_id, ALL_TEAMS_SCOPE) as connection:
            rows = connection.execute(
                select(metering_hourly_rollups)
                .where(metering_hourly_rollups.c.tenant_id == tenant_id)
                .where(metering_hourly_rollups.c.bucket_start >= period_start)
                .where(metering_hourly_rollups.c.bucket_start <= period_end)
                .order_by(metering_hourly_rollups.c.bucket_start.asc())
            ).mappings().all()
        return [HourlyUsageRollup.model_validate(row) for row in rows]

    def _export_rollups_csv(self, request: MeteringExportRequest) -> str:
        import csv
        from io import StringIO

        rollups = self._rollups_for_period(
            tenant_id=request.tenant_id,
            period_start=request.period_start,
            period_end=request.period_end,
        )
        buffer = StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                *(["schema_version"] if request.schema_version == "v2" else []),
                "rollup_id",
                "bucket_start",
                "tenant_id",
                "team_id",
                "role",
                "provider_id",
                "model_id",
                "rate_card_id",
                "request_count",
                "total_input_tokens",
                "total_output_tokens",
                "total_actual_cost_usd",
            ],
        )
        writer.writeheader()
        for rollup in rollups:
            row = {
                "rollup_id": rollup.rollup_id,
                "bucket_start": rollup.bucket_start.isoformat(),
                "tenant_id": rollup.tenant_id,
                "team_id": rollup.team_id,
                "role": rollup.role,
                "provider_id": rollup.provider_id,
                "model_id": rollup.model_id,
                "rate_card_id": rollup.rate_card_id,
                "request_count": rollup.request_count,
                "total_input_tokens": rollup.total_input_tokens,
                "total_output_tokens": rollup.total_output_tokens,
                "total_actual_cost_usd": f"{rollup.total_actual_cost_usd:.6f}",
            }
            if request.schema_version == "v2":
                row = {"schema_version": "v2", **row}
            writer.writerow(row)
        return buffer.getvalue()

    @contextmanager
    def _scoped_transaction(self, tenant_id: str, team_id: str) -> Iterator[Connection]:
        with self._engine.begin() as connection:
            for key, value in tenant_guc_values(tenant_id=tenant_id, team_id=team_id).items():
                connection.execute(
                    text("SELECT set_config(:key, :value, true)"),
                    {"key": key, "value": value},
                )
            yield connection


def build_metering_ledger(
    *,
    database_url: str | None,
    legacy_ledger: MeteringLedger | None,
    settings: MeteringLedgerSettings | None = None,
    logger: logging.Logger | None = None,
    telemetry: PersistenceTelemetry | None = None,
) -> MeteringLedger:
    resolved = settings or MeteringLedgerSettings.from_env()
    if resolved.mode == "legacy":
        if legacy_ledger is None:
            raise RuntimeError("Legacy metering-ledger mode requires an in-memory test double.")
        return legacy_ledger
    if not database_url:
        raise RuntimeError(
            f"{METERING_LEDGER_MODE_ENV_KEY}=postgres requires a configured database URL"
        )
    return PostgresMeteringLedger(database_url, logger=logger, telemetry=telemetry)


class PostgresModelCatalog:
    def __init__(
        self,
        database_url: str,
        *,
        bundle_path: str | None = None,
        engine: Engine | None = None,
        logger: logging.Logger | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self._engine = engine or create_engine(database_url, future=True, pool_pre_ping=True)
        self._logger = logger or logging.getLogger(__name__)
        self._bundle_path = bundle_path
        self._telemetry = telemetry or bootstrap_telemetry()
        try:
            self.reconcile_bundle()
        except Exception:
            self._logger.warning(
                "model_catalog_bootstrap_deferred",
                extra={"subsystem": "model_catalog"},
            )

    def resolve_model(
        self,
        model_id: str,
        deployment_profile: str,
    ):
        with self._telemetry.trace(
            "model_catalog_resolve_model",
            subsystem="model_catalog",
            operation="resolve_model",
            deployment_profile=deployment_profile,
        ):
            entries, _ = self._load_catalog_state()
            try:
                return entries[(model_id, deployment_profile)]
            except KeyError as exc:
                raise ValueError(
                    f"Unknown model `{model_id}` for deployment profile `{deployment_profile}`."
                ) from exc

    def validate_fallback(
        self,
        *,
        primary_model_id: str,
        fallback_model_id: str,
        deployment_profile: str,
    ) -> None:
        primary = self.resolve_model(primary_model_id, deployment_profile)
        self.resolve_model(fallback_model_id, deployment_profile)
        if fallback_model_id not in primary.allowed_fallback_targets:
            raise ValueError(
                f"Model `{fallback_model_id}` is not an allowed fallback for `{primary_model_id}`."
            )

    def effective_token_cap(
        self,
        *,
        role: str,
        model_id: str,
        deployment_profile: str,
        tenant_override=None,
    ):
        from backend.governance.catalog import TokenCap

        entry = self.resolve_model(model_id, deployment_profile)
        _, policies = self._load_catalog_state()
        role_policy = policies[role]
        input_limit = min(entry.max_input_tokens, role_policy.max_input_tokens)
        output_limit = min(entry.max_output_tokens, role_policy.max_output_tokens)
        if tenant_override is not None:
            input_limit = min(input_limit, tenant_override.input_tokens)
            output_limit = min(output_limit, tenant_override.output_tokens)
        return TokenCap(input_tokens=input_limit, output_tokens=output_limit)

    def reconcile_bundle(self) -> None:
        bundle = _load_catalog_bundle(self._bundle_path)
        entry_rows = {
            (entry["model_id"], entry["deployment_profile"]): entry
            for entry in bundle["entries"]
        }
        with self._engine.begin() as connection:
            existing = connection.execute(select(model_catalog_entries)).mappings().all()
            existing_ids = {
                (row["model_id"], row["deployment_profile"])
                for row in existing
            }
            changed = existing_ids != set(entry_rows)
            for entry in bundle["entries"]:
                stmt = pg_insert(model_catalog_entries).values(**entry)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        model_catalog_entries.c.model_id,
                        model_catalog_entries.c.deployment_profile,
                    ],
                    set_={
                        "provider_id": stmt.excluded.provider_id,
                        "max_input_tokens": stmt.excluded.max_input_tokens,
                        "max_output_tokens": stmt.excluded.max_output_tokens,
                        "default_price_card_id": stmt.excluded.default_price_card_id,
                        "supports_tools": stmt.excluded.supports_tools,
                        "supports_json_mode": stmt.excluded.supports_json_mode,
                        "supports_streaming": stmt.excluded.supports_streaming,
                        "allowed_fallback_targets": stmt.excluded.allowed_fallback_targets,
                        "updated_at": text("now()"),
                    },
                )
                connection.execute(stmt)

            policy_roles = {policy["role"] for policy in bundle["role_token_policies"]}
            existing_policy_roles = {
                row["role"]
                for row in connection.execute(select(role_token_policies)).mappings().all()
            }
            changed = changed or existing_policy_roles != policy_roles
            for policy in bundle["role_token_policies"]:
                stmt = pg_insert(role_token_policies).values(**policy)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[role_token_policies.c.role],
                    set_={
                        "max_input_tokens": stmt.excluded.max_input_tokens,
                        "max_output_tokens": stmt.excluded.max_output_tokens,
                        "updated_at": text("now()"),
                    },
                )
                connection.execute(stmt)

            if changed:
                connection.execute(
                    audit_events.insert().values(
                        event_id=str(uuid4()),
                        action="catalog_reconcile",
                        actor="system:persistence-factory",
                        rationale="seed bundled model catalog into PostgreSQL",
                        target_id="model_catalog_entries",
                        evidence_summary=f"models={len(bundle['entries'])}; roles={len(bundle['role_token_policies'])}",
                    )
                )

    def _load_catalog_state(self):
        from backend.governance.catalog import ModelCatalogEntry, RoleTokenPolicy

        with self._engine.begin() as connection:
            entries = connection.execute(select(model_catalog_entries)).mappings().all()
            policies = connection.execute(select(role_token_policies)).mappings().all()
        if not entries or not policies:
            self.reconcile_bundle()
            with self._engine.begin() as connection:
                entries = connection.execute(select(model_catalog_entries)).mappings().all()
                policies = connection.execute(select(role_token_policies)).mappings().all()
        return (
            {
                (row["model_id"], row["deployment_profile"]): ModelCatalogEntry.model_validate(row)
                for row in entries
            },
            {
                row["role"]: RoleTokenPolicy.model_validate(row)
                for row in policies
            },
        )


class RedisSharedProviderHealthStore:
    def __init__(
        self,
        database_url: str,
        *,
        redis_settings: RedisSettings | None = None,
        redis_client=None,
        engine: Engine | None = None,
        logger: logging.Logger | None = None,
        settings: ProviderHealthSettings | None = None,
        telemetry: PersistenceTelemetry | None = None,
    ) -> None:
        self.settings = settings or ProviderHealthSettings.from_env()
        self._engine = engine or create_engine(database_url, future=True, pool_pre_ping=True)
        self._redis = redis_client or build_redis_client(redis_settings or RedisSettings.from_env())
        self._logger = logger or logging.getLogger(__name__)
        self._telemetry = telemetry or bootstrap_telemetry()

    def snapshot(self, provider_id: str):
        with self._telemetry.trace(
            "provider_health_snapshot",
            subsystem="provider_health",
            operation="snapshot",
            provider_id=provider_id,
        ):
            try:
                state, failures, probes = self._read_state(provider_id)
            except Exception:
                state = (
                    ProviderHealthState.OPEN
                    if self.settings.fail_closed_without_redis
                    else ProviderHealthState.CLOSED
                )
                failures = self.settings.failure_threshold
                probes = 0
            self._telemetry.set_gauge(
                "devsquad_provider_circuit_breaker_state",
                1.0 if state == ProviderHealthState.CLOSED else 0.0,
                provider_id=provider_id,
            )
            return ProviderHealthSnapshot(
                provider_id=provider_id,
                state=state,
                consecutive_failures=failures,
                remaining_probe_attempts=probes,
            )

    def record_failure(self, provider_id: str) -> None:
        state, failures, probes = self._apply_provider_script(
            provider_id,
            _PROVIDER_FAILURE_SCRIPT,
            self.settings.failure_threshold,
            event_kind="failure",
        )
        self._persist_event(provider_id, "failure", state, failures, probes)

    def record_success(self, provider_id: str) -> None:
        state, failures, probes = self._apply_provider_script(
            provider_id,
            _PROVIDER_SUCCESS_SCRIPT,
            event_kind="success",
        )
        self._persist_event(provider_id, "success", state, failures, probes)

    def move_to_half_open(self, provider_id: str) -> None:
        state, failures, probes = self._apply_provider_script(
            provider_id,
            _PROVIDER_HALF_OPEN_SCRIPT,
            self.settings.recovery_probe_limit,
            event_kind="half_open",
        )
        self._persist_event(provider_id, "half_open", state, failures, probes)

    def allow_request(self, provider_id: str) -> bool:
        try:
            result = self._redis.eval(
                _PROVIDER_ALLOW_REQUEST_SCRIPT,
                1,
                _provider_key(provider_id),
            )
            allowed = bool(int(result[0]))
            state = ProviderHealthState(str(result[1]))
            failures = int(result[2])
            probes = int(result[3])
        except Exception:
            allowed = not self.settings.fail_closed_without_redis
            state = ProviderHealthState.OPEN if not allowed else ProviderHealthState.CLOSED
            failures = self.settings.failure_threshold
            probes = 0
            self._logger.warning(
                "provider_health_allow_request_fallback",
                extra={"provider_id": provider_id, "subsystem": "provider_health"},
            )
        self._telemetry.set_gauge(
            "devsquad_provider_circuit_breaker_state",
            1.0 if allowed else 0.0,
            provider_id=provider_id,
        )
        self._persist_event(provider_id, "allow_request", state, failures, probes)
        return allowed

    def _apply_provider_script(self, provider_id: str, script: str, *args: object, event_kind: str):
        try:
            result = self._redis.eval(script, 1, _provider_key(provider_id), *args)
            state = ProviderHealthState(str(result[0]))
            failures = int(result[1])
            probes = int(result[2])
            return state, failures, probes
        except Exception as exc:
            fallback_state = (
                ProviderHealthState.OPEN
                if self.settings.fail_closed_without_redis
                else ProviderHealthState.CLOSED
            )
            self._persist_event(
                provider_id,
                event_kind,
                fallback_state,
                self.settings.failure_threshold,
                0,
                error=str(exc),
            )
            return fallback_state, self.settings.failure_threshold, 0

    def _read_state(self, provider_id: str):
        raw_state = self._redis.hget(_provider_key(provider_id), "state") or ProviderHealthState.CLOSED.value
        raw_failures = self._redis.hget(_provider_key(provider_id), "consecutive_failures") or "0"
        raw_probes = self._redis.hget(_provider_key(provider_id), "remaining_probe_attempts") or "0"
        return ProviderHealthState(raw_state), int(raw_failures), int(raw_probes)

    def _persist_event(
        self,
        provider_id: str,
        event_kind: str,
        state: ProviderHealthState,
        consecutive_failures: int,
        remaining_probe_attempts: int,
        *,
        error: str | None = None,
    ) -> None:
        summary = (
            f"state={state.value}; failures={consecutive_failures}; probes={remaining_probe_attempts}"
            if error is None
            else f"fallback={state.value}; error={error}"
        )
        with self._engine.begin() as connection:
            connection.execute(
                provider_health_events.insert().values(
                    provider_id=provider_id,
                    event_kind=event_kind,
                    state=state.value,
                    consecutive_failures=consecutive_failures,
                    remaining_probe_attempts=remaining_probe_attempts,
                    evidence_summary=summary,
                )
            )


def build_model_catalog(
    *,
    database_url: str | None,
    legacy_catalog=None,
    settings: ModelCatalogSettings | None = None,
    logger: logging.Logger | None = None,
    telemetry: PersistenceTelemetry | None = None,
):
    resolved = settings or ModelCatalogSettings.from_env()
    if resolved.mode == "legacy":
        if legacy_catalog is None:
            raise RuntimeError("Legacy model-catalog mode requires an in-memory test double.")
        return legacy_catalog
    if not database_url:
        raise RuntimeError(f"{MODEL_CATALOG_MODE_ENV_KEY}=postgres requires a configured database URL")
    return PostgresModelCatalog(
        database_url,
        bundle_path=resolved.bundle_path,
        logger=logger,
        telemetry=telemetry,
    )


def build_provider_health_store(
    *,
    database_url: str | None,
    redis_settings: RedisSettings,
    legacy_store=None,
    settings: ProviderHealthSettings | None = None,
    logger: logging.Logger | None = None,
    telemetry: PersistenceTelemetry | None = None,
):
    resolved = settings or ProviderHealthSettings.from_env()
    if resolved.mode == "legacy":
        if legacy_store is None:
            raise RuntimeError("Legacy provider-health mode requires an in-memory test double.")
        return legacy_store
    if not database_url:
        raise RuntimeError(
            f"{PROVIDER_HEALTH_STORE_MODE_ENV_KEY}=redis requires a configured database URL"
        )
    if not redis_settings.configured:
        raise RuntimeError(
            f"{PROVIDER_HEALTH_STORE_MODE_ENV_KEY}=redis requires a configured Redis URL"
        )
    return RedisSharedProviderHealthStore(
        database_url,
        redis_settings=redis_settings,
        logger=logger,
        settings=resolved,
        telemetry=telemetry,
    )


def _counter_keys(context: BudgetContext, now: datetime) -> tuple[str, str, str]:
    return (
        f"budget:ticket:{context.run_id}",
        f"budget:team:daily:{context.tenant_id}:{context.team_id}:{now:%Y%m%d}",
        f"budget:team:monthly:{context.tenant_id}:{context.team_id}:{now:%Y%m}",
    )


def _usd_to_cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _cents_to_usd(cents: int) -> Decimal:
    return (Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"))


def _provider_key(provider_id: str) -> str:
    return f"provider_health:{provider_id}"


def _load_catalog_bundle(bundle_path: str | None) -> dict[str, object]:
    if bundle_path:
        raw = open(bundle_path, encoding="utf-8").read()
    else:
        raw = files("backend.persistence").joinpath("model_catalog.yaml").read_text(encoding="utf-8")
    return json.loads(raw)
