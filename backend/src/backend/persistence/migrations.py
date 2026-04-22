from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import BaseModel
from sqlalchemy import create_engine

from alembic import command

from .db import DatabaseSettings


class MigrationStatus(BaseModel):
    state: Literal["not_configured", "skipped", "up_to_date", "upgraded"]
    expected_revision: str | None = None
    current_revision: str | None = None
    reason: str | None = None


class MigrationRunner:
    def __init__(self, settings: DatabaseSettings | None = None) -> None:
        self.settings = settings or DatabaseSettings.from_env()

    def ensure_current(self) -> MigrationStatus:
        expected_revision = get_head_revision()
        if not self.settings.configured:
            return MigrationStatus(
                state="not_configured",
                expected_revision=expected_revision,
                reason="database_url_missing",
            )

        current_revision = get_current_revision(self.settings.sync_url())
        if self.settings.air_gapped_skip_migrations:
            return MigrationStatus(
                state="skipped",
                expected_revision=expected_revision,
                current_revision=current_revision,
                reason="air_gapped_preseeded_database",
            )

        if current_revision == expected_revision:
            return MigrationStatus(
                state="up_to_date",
                expected_revision=expected_revision,
                current_revision=current_revision,
            )

        command.upgrade(build_alembic_config(self.settings.sync_url()), "head")
        return MigrationStatus(
            state="upgraded",
            expected_revision=expected_revision,
            current_revision=get_current_revision(self.settings.sync_url()),
        )


def build_alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(resolve_alembic_ini_path()))
    if database_url is not None:
        set_alembic_url(config, database_url)
    return config


def set_alembic_url(config: Config, database_url: str) -> None:
    # Alembic stores config via configparser, which treats `%` as interpolation.
    # URL-encoded socket paths (e.g. /var/folders/...) contain `%` and must be escaped.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))


def get_head_revision() -> str | None:
    script = ScriptDirectory.from_config(build_alembic_config())
    return script.get_current_head()


def get_current_revision(database_url: str) -> str | None:
    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()
    finally:
        engine.dispose()


def resolve_alembic_ini_path() -> Path:
    env_path = os.getenv("BACKEND_ALEMBIC_INI")
    candidates = [
        Path(env_path) if env_path else None,
        Path.cwd() / "alembic.ini",
        Path.cwd() / "backend" / "alembic.ini",
        Path(__file__).resolve().parents[3] / "alembic.ini",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    raise FileNotFoundError("Unable to locate alembic.ini for backend migrations.")
