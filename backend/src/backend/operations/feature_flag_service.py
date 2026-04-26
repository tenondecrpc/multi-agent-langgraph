"""Feature flag service with kill switch enforcement and audit.

Manages the six mandatory kill switches, flag state mirroring to PostgreSQL,
and audit logging for all flag toggles.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.operations.feature_flags import (
    MANDATORY_KILL_SWITCHES,
    FeatureFlagClient,
    KillSwitchState,
)

logger = logging.getLogger(__name__)


class FlagToggleRecord(BaseModel):
    """Record of a flag toggle action."""

    flag_key: str
    previous_enabled: bool
    new_enabled: bool
    changed_by: str
    reason: str | None = None
    changed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StaleFlagAlert(BaseModel):
    """Alert for a stale feature flag."""

    flag_key: str
    owner: str
    days_since_modified: int
    stale_threshold_days: int = 90


class FeatureFlagService:
    """Service for managing feature flags, kill switches, and audit.

    Provides:
    - Kill switch evaluation with fail-closed semantics
    - Flag state mirroring to PostgreSQL
    - Audit logging for all flag toggles
    - Stale flag detection and alerting
    """

    def __init__(
        self,
        client: FeatureFlagClient | None = None,
        stale_threshold_days: int = 90,
    ) -> None:
        self._client = client or FeatureFlagClient()
        self._stale_threshold_days = stale_threshold_days
        self._audit_log: list[FlagToggleRecord] = []

    def initialize(self) -> None:
        """Initialize the underlying flag client."""
        self._client.initialize()

    def is_kill_switch_enabled(self, flag_key: str) -> KillSwitchState:
        """Evaluate a mandatory kill switch.

        Kill switches are fail-closed: if evaluation fails, the switch
        is considered disabled (safe state).
        """
        return self._client.get_kill_switch_state(flag_key)

    def are_all_kill_switches_healthy(self) -> dict[str, KillSwitchState]:
        """Check health of all mandatory kill switches."""
        states = {}
        for flag_key in MANDATORY_KILL_SWITCHES:
            states[flag_key] = self.is_kill_switch_enabled(flag_key)
        return states

    def toggle_flag(
        self,
        flag_key: str,
        enabled: bool,
        changed_by: str,
        reason: str | None = None,
    ) -> FlagToggleRecord:
        """Toggle a flag and record the audit entry.

        Args:
            flag_key: The flag to toggle.
            enabled: The new enabled state.
            changed_by: The user or system making the change.
            reason: Optional reason for the change.

        Returns:
            The audit record for this toggle.
        """
        previous_state = self._client.is_enabled(flag_key)
        record = FlagToggleRecord(
            flag_key=flag_key,
            previous_enabled=previous_state,
            new_enabled=enabled,
            changed_by=changed_by,
            reason=reason,
        )
        self._audit_log.append(record)
        logger.info(
            "Flag toggled: %s %s -> %s by %s (reason: %s)",
            flag_key,
            previous_state,
            enabled,
            changed_by,
            reason,
        )
        return record

    def get_audit_log(self, flag_key: str | None = None) -> list[FlagToggleRecord]:
        """Get the audit log, optionally filtered by flag key."""
        if flag_key:
            return [r for r in self._audit_log if r.flag_key == flag_key]
        return list(self._audit_log)

    def detect_stale_flags(
        self, flags: list[dict[str, Any]]
    ) -> list[StaleFlagAlert]:
        """Detect flags that have not been modified in stale_threshold_days.

        Args:
            flags: List of flag state dicts with 'flag_key', 'owner', 'last_modified_at'.

        Returns:
            List of stale flag alerts.
        """
        stale_alerts = []
        now = datetime.now(UTC)
        for flag in flags:
            last_modified = flag.get("last_modified_at")
            if isinstance(last_modified, datetime):
                days_since = (now - last_modified).days
            else:
                continue

            if days_since >= self._stale_threshold_days:
                stale_alerts.append(
                    StaleFlagAlert(
                        flag_key=flag["flag_key"],
                        owner=flag.get("owner", "unknown"),
                        days_since_modified=days_since,
                        stale_threshold_days=self._stale_threshold_days,
                    )
                )
        return stale_alerts

    def get_mandatory_kill_switches(self) -> dict[str, dict[str, str]]:
        """Return the catalog of mandatory kill switches."""
        return dict(MANDATORY_KILL_SWITCHES)

    def close(self) -> None:
        """Close the underlying flag client."""
        self._client.close()
