from __future__ import annotations

import os

from pydantic import BaseModel, Field
from sqlalchemy.engine import make_url

DEFAULT_DATABASE_URL = "postgresql://not-configured"
ALL_TENANTS_SCOPE = "*"
ALL_TEAMS_SCOPE = "*"
DATABASE_URL_ENV_KEYS = ("BACKEND_DATABASE_URL", "DATABASE_URL")
SKIP_MIGRATIONS_ENV_KEYS = (
    "BACKEND_AIR_GAPPED_SKIP_MIGRATIONS",
    "BACKEND_SKIP_STARTUP_MIGRATIONS",
)


class DatabaseSettings(BaseModel):
    url: str = DEFAULT_DATABASE_URL
    pool_size: int = 10
    statement_timeout_ms: int = 5_000
    air_gapped_skip_migrations: bool = False

    @property
    def configured(self) -> bool:
        return self.url != DEFAULT_DATABASE_URL

    @classmethod
    def from_env(cls) -> DatabaseSettings:
        return cls(
            url=_first_env(DATABASE_URL_ENV_KEYS, DEFAULT_DATABASE_URL),
            air_gapped_skip_migrations=_env_flag(SKIP_MIGRATIONS_ENV_KEYS),
        )

    def sync_url(self) -> str:
        return make_sync_database_url(self.url)


class DatabaseRuntime(BaseModel):
    dialect: str = "postgresql"
    configured: bool = False
    settings: DatabaseSettings = Field(default_factory=DatabaseSettings)


def build_database_runtime(settings: DatabaseSettings | None = None) -> DatabaseRuntime:
    resolved_settings = settings or DatabaseSettings.from_env()
    return DatabaseRuntime(
        configured=resolved_settings.configured,
        settings=resolved_settings,
    )


def make_sync_database_url(url: str) -> str:
    if url == DEFAULT_DATABASE_URL:
        return url

    parsed = make_url(url)
    drivername = parsed.drivername
    if drivername in {"postgres", "postgresql", "postgresql+psycopg"}:
        return parsed.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    if drivername == "postgresql+asyncpg":
        return parsed.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    return url


def tenant_guc_values(*, tenant_id: str, team_id: str) -> dict[str, str]:
    return {
        "app.tenant_id": tenant_id,
        "app.team_id": team_id,
    }


def _first_env(keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


def _env_flag(keys: tuple[str, ...]) -> bool:
    truthy = {"1", "true", "yes", "on"}
    return any(os.getenv(key, "").strip().lower() in truthy for key in keys)
