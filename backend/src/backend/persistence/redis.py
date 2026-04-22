from __future__ import annotations

import os

from pydantic import BaseModel, Field
from redis import Redis

DEFAULT_REDIS_URL = "redis://not-configured"
REDIS_URL_ENV_KEYS = ("BACKEND_REDIS_URL", "REDIS_URL")


class RedisSettings(BaseModel):
    url: str = DEFAULT_REDIS_URL
    max_connections: int = 20
    cluster_mode: bool = False
    tls_enabled: bool = False

    @property
    def configured(self) -> bool:
        return self.url != DEFAULT_REDIS_URL

    @classmethod
    def from_env(cls) -> RedisSettings:
        return cls(url=_first_env(REDIS_URL_ENV_KEYS, DEFAULT_REDIS_URL))


class RedisRuntime(BaseModel):
    configured: bool = False
    settings: RedisSettings = Field(default_factory=RedisSettings)


def build_redis_runtime(settings: RedisSettings | None = None) -> RedisRuntime:
    resolved_settings = settings or RedisSettings.from_env()
    return RedisRuntime(
        configured=resolved_settings.configured,
        settings=resolved_settings,
    )


def build_redis_client(settings: RedisSettings) -> Redis:
    return Redis.from_url(
        settings.url,
        decode_responses=True,
        health_check_interval=0,
        lib_name=None,
        lib_version=None,
        protocol=2,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )


def _first_env(keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default
