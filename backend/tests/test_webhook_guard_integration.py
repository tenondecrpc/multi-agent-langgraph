from __future__ import annotations

import socketserver
import subprocess
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus

import psycopg
import pytest
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from alembic import command
from backend.persistence import build_alembic_config
from backend.persistence.redis import RedisSettings
from backend.persistence.webhook import (
    PostgresRedisWebhookGuard,
    RedisWebhookDedupeCache,
    SqlAlchemyWebhookIdempotencyStore,
)
from backend.security.webhook import WebhookRequest


class _MiniRedisServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _MiniRedisHandler)
        self._store: dict[str, tuple[str, float | None]] = {}
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._stopped = False

    @property
    def url(self) -> str:
        host, port = self.server_address
        return f"redis://{host}:{port}/0"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self.shutdown()
        self.server_close()
        if self._thread.is_alive():
            self._thread.join(timeout=1)

    def exists(self, key: str) -> bool:
        self._purge_expired()
        return key in self._store

    def set(self, key: str, value: str, *, ttl_seconds: int | None) -> None:
        expires_at = None if ttl_seconds is None else time.monotonic() + ttl_seconds
        self._store[key] = (value, expires_at)

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [
            key
            for key, (_, expires_at) in self._store.items()
            if expires_at is not None and expires_at <= now
        ]
        for key in expired:
            self._store.pop(key, None)


class _MiniRedisHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        server = self.server
        while True:
            command = self._read_command()
            if command is None:
                return

            name = command[0].upper()
            if name == "PING":
                self.wfile.write(b"+PONG\r\n")
            elif name == "EXISTS":
                count = int(sum(1 for key in command[1:] if server.exists(key)))
                self.wfile.write(f":{count}\r\n".encode())
            elif name == "SET":
                ttl_seconds = _parse_set_expiry(command)
                server.set(command[1], command[2], ttl_seconds=ttl_seconds)
                self.wfile.write(b"+OK\r\n")
            elif name == "CLIENT":
                self.wfile.write(b"+OK\r\n")
            elif name == "SELECT":
                self.wfile.write(b"+OK\r\n")
            elif name == "QUIT":
                self.wfile.write(b"+OK\r\n")
                self.wfile.flush()
                return
            else:
                self.wfile.write(b"+OK\r\n")
            self.wfile.flush()

    def _read_command(self) -> list[str] | None:
        first = self.rfile.read(1)
        if not first:
            return None
        if first != b"*":
            raise ValueError("expected RESP array")

        arg_count = int(self.rfile.readline().strip())
        values: list[str] = []
        for _ in range(arg_count):
            if self.rfile.read(1) != b"$":
                raise ValueError("expected RESP bulk string")
            item_length = int(self.rfile.readline().strip())
            values.append(self.rfile.read(item_length).decode())
            if self.rfile.read(2) != b"\r\n":
                raise ValueError("expected RESP line terminator")
        return values


def _parse_set_expiry(command: list[str]) -> int | None:
    upper_command = [item.upper() for item in command]
    if "EX" not in upper_command:
        return None
    expiry_index = upper_command.index("EX")
    return int(command[expiry_index + 1])


@pytest.fixture()
def temporary_postgres() -> str:
    with TemporaryDirectory(prefix="backend-pg-") as temp_dir:
        base_dir = Path(temp_dir)
        data_dir = base_dir / "data"
        log_path = base_dir / "postgres.log"
        socket_dir = base_dir / "socket"
        socket_dir.mkdir(parents=True, exist_ok=True)
        port = 55432

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
def temporary_redis() -> _MiniRedisServer:
    server = _MiniRedisServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()


def test_postgres_redis_webhook_guard_records_metadata_and_deduplicates(
    temporary_postgres: str,
    temporary_redis: _MiniRedisServer,
) -> None:
    command.upgrade(build_alembic_config(temporary_postgres), "head")
    guard = _build_guard(temporary_postgres, temporary_redis.url)
    request = _signed_request(guard, event_id="evt-1")

    accepted = guard.verify(request, now=1_000)
    duplicate = guard.verify(request, now=1_001)

    assert accepted.accepted is True
    assert accepted.deduplicated is False
    assert duplicate.accepted is True
    assert duplicate.deduplicated is True

    with _connect(temporary_postgres) as connection:
        count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM webhook_idempotency_records"
        ).fetchone()
        record = connection.execute(
            """
            SELECT
                source,
                delivery_id,
                tenant_id,
                team_id,
                endpoint,
                hmac_digest,
                disposition_status
            FROM webhook_idempotency_records
            """
        ).fetchone()

    assert count_row["count"] == 1
    assert dict(record) == {
        "source": "jira",
        "delivery_id": "evt-1",
        "tenant_id": "tenant-alpha",
        "team_id": "team-core",
        "endpoint": "/api/v1/webhooks/jira",
        "hmac_digest": request.signature,
        "disposition_status": "accepted",
    }


def test_postgres_redis_webhook_guard_redis_outage_falls_back_to_postgres_unique_constraint(
    temporary_postgres: str,
    temporary_redis: _MiniRedisServer,
) -> None:
    command.upgrade(build_alembic_config(temporary_postgres), "head")
    guard = _build_guard(temporary_postgres, temporary_redis.url)
    request = _signed_request(guard, event_id="evt-2")

    first = guard.verify(request, now=1_000)
    temporary_redis.stop()
    duplicate = guard.verify(request, now=1_001)

    assert first.accepted is True
    assert first.deduplicated is False
    assert duplicate.accepted is True
    assert duplicate.deduplicated is True

    with _connect(temporary_postgres) as connection:
        count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM webhook_idempotency_records"
        ).fetchone()

    assert count_row["count"] == 1


def _build_guard(database_url: str, redis_url: str) -> PostgresRedisWebhookGuard:
    return PostgresRedisWebhookGuard(
        secret="shared-secret",
        record_store=SqlAlchemyWebhookIdempotencyStore(database_url),
        dedupe_cache=RedisWebhookDedupeCache(
            redis_settings=RedisSettings(url=redis_url),
        ),
        freshness_window_seconds=300,
    )


def _signed_request(guard: PostgresRedisWebhookGuard, *, event_id: str) -> WebhookRequest:
    request = WebhookRequest(
        body='{"ticket":"ENG-1"}',
        signature="",
        timestamp=1_000,
        event_id=event_id,
        tenant_id="tenant-alpha",
        team_id="team-core",
        remote_addr="10.0.0.1",
    )
    request.signature = guard.sign(request.body, request.timestamp)
    return request


def _connect(database_url: str) -> psycopg.Connection:
    parsed = make_url(database_url)
    socket_path = parsed.query.get("host", "")
    port = parsed.query.get("port", "")
    user = parsed.username or "postgres"
    database = parsed.database or "postgres"
    return psycopg.connect(
        f"dbname={database} user={user} host={socket_path} port={port}",
        autocommit=True,
        row_factory=dict_row,
    )


def _run(command_args: list[str]) -> None:
    subprocess.run(command_args, check=True, capture_output=True, text=True)
