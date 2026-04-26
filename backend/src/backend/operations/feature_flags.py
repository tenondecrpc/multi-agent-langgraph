"""OpenFeature-based feature flag client wrapper.

Provides a unified interface for feature flag evaluation across
Unleash (self-hosted) and LaunchDarkly (customer-owned) providers.
Includes PostgreSQL mirror for fail-safe access when the flag
service is unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FlagProvider(Enum):
    UNLEASH = "unleash"
    LAUNCHDARKLY = "launchdarkly"
    POSTGRES_MIRROR = "postgres_mirror"


@dataclass
class FlagEvaluation:
    """Result of a feature flag evaluation."""

    flag_key: str
    enabled: bool
    variant: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: FlagProvider = FlagProvider.UNLEASH


@dataclass
class KillSwitchState:
    """State of a mandatory kill switch."""

    flag_key: str
    enabled: bool
    owner: str
    description: str
    last_modified: datetime
    modified_by: str = "system"


MANDATORY_KILL_SWITCHES: dict[str, dict[str, str]] = {
    "llm_provider_anthropic": {
        "owner": "llm-governance",
        "description": "Kill switch for Anthropic provider routing",
    },
    "llm_provider_openai": {
        "owner": "llm-governance",
        "description": "Kill switch for OpenAI provider routing",
    },
    "pr_creation": {
        "owner": "runtime-pipeline",
        "description": "Kill switch for PR creation node",
    },
    "graph_activation": {
        "owner": "runtime-pipeline",
        "description": "Kill switch for graph execution activation",
    },
    "sandbox_runtime_gvisor": {
        "owner": "sandbox-execution",
        "description": "Kill switch for gVisor sandbox runtime",
    },
    "ticket_processing": {
        "owner": "runtime-pipeline",
        "description": "Global kill switch for ticket processing",
    },
}


class FeatureFlagClient:
    """Feature flag client with provider failover to PostgreSQL mirror.

    Evaluates flags against the primary provider (Unleash or LaunchDarkly).
    If the provider is unavailable, falls back to the PostgreSQL mirror
    with TTL-based staleness detection.
    """

    def __init__(
        self,
        provider: FlagProvider = FlagProvider.UNLEASH,
        app_name: str = "langgraph-dev-squad",
        environment: str = "default",
    ) -> None:
        self._provider = provider
        self._app_name = app_name
        self._environment = environment
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the flag client connection."""
        self._initialized = True
        logger.info("Feature flag client initialized (provider=%s)", self._provider.value)

    def is_enabled(self, flag_key: str, context: dict[str, Any] | None = None) -> bool:
        """Evaluate whether a flag is enabled for the given context.

        Falls back to PostgreSQL mirror if primary provider is unavailable.
        """
        if not self._initialized:
            self.initialize()

        try:
            return self._evaluate_primary(flag_key, context or {})
        except Exception as exc:
            logger.warning(
                "Primary flag provider unavailable, falling back to mirror: %s", exc
            )
            return self._evaluate_mirror(flag_key, context or {})

    def get_kill_switch_state(self, flag_key: str) -> KillSwitchState:
        """Get the state of a mandatory kill switch.

        Kill switches are fail-closed: if evaluation fails, return disabled.
        """
        if flag_key not in MANDATORY_KILL_SWITCHES:
            raise ValueError(f"Unknown kill switch: {flag_key}")

        meta = MANDATORY_KILL_SWITCHES[flag_key]
        try:
            enabled = self.is_enabled(flag_key)
            return KillSwitchState(
                flag_key=flag_key,
                enabled=enabled,
                owner=meta["owner"],
                description=meta["description"],
                last_modified=datetime.now(UTC),
            )
        except Exception as exc:
            logger.error("Kill switch evaluation failed (fail-closed): %s", exc)
            return KillSwitchState(
                flag_key=flag_key,
                enabled=False,
                owner=meta["owner"],
                description=meta["description"],
                last_modified=datetime.now(UTC),
            )

    def _evaluate_primary(self, flag_key: str, context: dict[str, Any]) -> bool:
        """Evaluate flag against primary provider."""
        if self._provider == FlagProvider.UNLEASH:
            return self._evaluate_unleash(flag_key, context)
        elif self._provider == FlagProvider.LAUNCHDARKLY:
            return self._evaluate_launchdarkly(flag_key, context)
        else:
            raise ValueError(f"Unsupported primary provider: {self._provider}")

    def _evaluate_unleash(self, flag_key: str, context: dict[str, Any]) -> bool:
        """Evaluate flag via Unleash SDK."""
        # TODO: Wire actual Unleash SDK
        # from UnleashClient import UnleashClient
        # client = UnleashClient(url=..., app_name=self._app_name)
        # return client.is_enabled(flag_key, context=context)
        logger.debug("Unleash evaluation (stub): flag=%s", flag_key)
        return True

    def _evaluate_launchdarkly(self, flag_key: str, context: dict[str, Any]) -> bool:
        """Evaluate flag via LaunchDarkly SDK."""
        # TODO: Wire actual LaunchDarkly SDK
        # import ldclient
        # from ldclient import LDConfig, Context
        # client = ldclient.get()
        # return client.variation(flag_key, context, False)
        logger.debug("LaunchDarkly evaluation (stub): flag=%s", flag_key)
        return True

    def _evaluate_mirror(self, flag_key: str, context: dict[str, Any]) -> bool:
        """Evaluate flag via PostgreSQL mirror (fail-safe)."""
        # TODO: Query feature_flag_state table with TTL check
        # SELECT enabled, updated_at FROM feature_flag_state WHERE flag_key = ?
        # If updated_at < NOW() - TTL, return default (False for kill switches)
        logger.debug("Mirror evaluation (stub): flag=%s", flag_key)
        return False

    def close(self) -> None:
        """Close the flag client connection."""
        self._initialized = False
        logger.info("Feature flag client closed")
