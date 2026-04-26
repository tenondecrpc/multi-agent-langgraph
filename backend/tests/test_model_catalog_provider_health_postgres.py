from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus

import psycopg
import pytest
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from alembic import command
from backend.governance.catalog import TokenCap
from backend.persistence import (
    PostgresModelCatalog,
    ProviderHealthSettings,
    RedisSharedProviderHealthStore,
    build_alembic_config,
)
from backend.persistence.redis import RedisSettings


class FakeRedis:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hashes: dict[str, dict[str, str]] = {}

    def eval(self, script: str, numkeys: int, *keys_and_args):
        del numkeys
        key = str(keys_and_args[0])
        args = keys_and_args[1:]
        hash_map = self._hashes.setdefault(key, {})
        with self._lock:
            if "consecutive_failures" in script and "threshold" in script:
                threshold = int(args[0])
                failures = int(hash_map.get("consecutive_failures", "0")) + 1
                state = "open" if failures >= threshold else "closed"
                hash_map["state"] = state
                hash_map["consecutive_failures"] = str(failures)
                hash_map["remaining_probe_attempts"] = "0"
                return [state, failures, 0]
            if "remaining_probe_attempts', probes" in script:
                probes = int(args[0])
                failures = int(hash_map.get("consecutive_failures", "0"))
                hash_map["state"] = "half_open"
                hash_map["remaining_probe_attempts"] = str(probes)
                return ["half_open", failures, probes]
            if "state', 'closed'" in script:
                hash_map["state"] = "closed"
                hash_map["consecutive_failures"] = "0"
                hash_map["remaining_probe_attempts"] = "0"
                return ["closed", 0, 0]
            state = hash_map.get("state", "closed")
            failures = int(hash_map.get("consecutive_failures", "0"))
            probes = int(hash_map.get("remaining_probe_attempts", "0"))
            if state == "open":
                return [0, state, failures, probes]
            if state == "half_open":
                if probes <= 0:
                    return [0, state, failures, probes]
                probes -= 1
                hash_map["remaining_probe_attempts"] = str(probes)
                return [1, state, failures, probes]
            return [1, state, failures, probes]

    def hget(self, name: str, key: str) -> str | None:
        with self._lock:
            return self._hashes.get(name, {}).get(key)


class FailingRedis:
    def eval(self, script: str, numkeys: int, *keys_and_args):
        del script, numkeys, keys_and_args
        raise RuntimeError("redis unavailable")

    def hget(self, name: str, key: str) -> str | None:
        del name, key
        raise RuntimeError("redis unavailable")


@pytest.fixture()
def temporary_postgres() -> str:
    with TemporaryDirectory(prefix="backend-pg-") as temp_dir:
        base_dir = Path(temp_dir)
        data_dir = base_dir / "data"
        log_path = base_dir / "postgres.log"
        socket_dir = base_dir / "socket"
        socket_dir.mkdir(parents=True, exist_ok=True)
        port = 55438

        try:
            _run(["initdb", "-D", str(data_dir), "-U", "postgres", "-A", "trust"])
            _run(
                [
                    "pg_ctl",
                    "-D",
                    str(data_dir),
                    "-l",
                    str(log_path),
                    "-o",
                    f"-p {port} -k {socket_dir} -c listen_addresses=",
                    "-w",
                    "start",
                ]
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip().splitlines()
            detail = stderr[-1] if stderr else str(exc)
            pytest.skip(f"ephemeral postgres bootstrap unavailable in this environment: {detail}")
        try:
            quoted_socket_dir = quote_plus(str(socket_dir))
            yield f"postgresql+psycopg://postgres@/postgres?host={quoted_socket_dir}&port={port}"
        finally:
            if data_dir.exists():
                subprocess.run(
                    ["pg_ctl", "-D", str(data_dir), "-m", "immediate", "stop"],
                    check=False,
                    capture_output=True,
                    text=True,
                )


@pytest.fixture()
def migrated_postgres(temporary_postgres: str) -> str:
    command.upgrade(build_alembic_config(temporary_postgres), "head")
    return temporary_postgres


def test_postgres_model_catalog_seeds_bundle_and_applies_token_caps(migrated_postgres: str) -> None:
    catalog = PostgresModelCatalog(migrated_postgres)

    entry = catalog.resolve_model("gpt-4.1", "connected")
    cap = catalog.effective_token_cap(
        role="coder",
        model_id="gpt-4.1",
        deployment_profile="connected",
        tenant_override=TokenCap(input_tokens=10000, output_tokens=2500),
    )

    assert entry.provider_id == "openai"
    assert "llama3.1" in entry.allowed_fallback_targets
    assert cap.input_tokens == 10000
    assert cap.output_tokens == 2500

    with _connect(migrated_postgres) as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM model_catalog_entries"
        ).fetchone()
    assert row["count"] >= 3


def test_redis_provider_health_store_persists_incident_evidence(migrated_postgres: str) -> None:
    redis = FakeRedis()
    store = RedisSharedProviderHealthStore(
        migrated_postgres,
        redis_client=redis,
        redis_settings=RedisSettings(url="redis://127.0.0.1:6379/0"),
    )

    store.record_failure("openai")
    store.record_failure("openai")
    snapshot = store.snapshot("openai")
    assert snapshot.state.value == "open"
    assert store.allow_request("openai") is False

    store.move_to_half_open("openai")
    assert store.allow_request("openai") is True

    store.record_success("openai")
    assert store.snapshot("openai").state.value == "closed"

    with _connect(migrated_postgres) as connection:
        count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM provider_health_events WHERE provider_id = 'openai'"
        ).fetchone()

    assert count_row["count"] >= 5


def test_air_gapped_provider_health_store_fails_closed_without_redis(
    migrated_postgres: str,
) -> None:
    store = RedisSharedProviderHealthStore(
        migrated_postgres,
        redis_client=FailingRedis(),
        redis_settings=RedisSettings(url="redis://127.0.0.1:6379/0"),
        settings=ProviderHealthSettings(
            mode="redis",
            deployment_profile="air_gapped",
            failure_threshold=2,
            recovery_probe_limit=1,
        ),
    )

    assert store.allow_request("vllm") is False
    assert store.snapshot("vllm").state.value == "open"


def _connect(database_url: str):
    parsed = make_url(database_url)
    return psycopg.connect(
        host=parsed.query.get("host") or parsed.host,
        port=parsed.query.get("port") or parsed.port,
        dbname=parsed.database,
        user=parsed.username,
        password=parsed.password,
        row_factory=dict_row,
        autocommit=True,
    )


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)
