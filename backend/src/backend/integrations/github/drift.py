from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from .permissions import hash_permissions, parse_github_permissions

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DriftEvent:
    installation_id: str
    tenant_id: str
    team_id: str
    previous_hash: str
    current_hash: str
    current_permissions: dict[str, str]


class InstallationRepository(Protocol):
    def list_active(self) -> list[object]: ...
    def mark_drift(self, installation_id: str) -> None: ...
    def acknowledge_drift(self, installation_id: str, *, actor: str) -> None: ...


class GitHubPermissionsAPI(Protocol):
    def get_installation_permissions(
        self,
        *,
        github_installation_id: int,
        base_url: str,
        jwt: str,
    ) -> dict[str, str]: ...


class PermissionDriftScanner:
    """Scheduled job that detects GitHub App permission drift.

    When drift is detected:
    - Emits a structured `github_permission_drift` log event (consumed by alerting)
    - Marks the installation as drift_acknowledged=False, which blocks mint calls
    - Records require super_admin acknowledgement to re-enable minting
    """

    def __init__(
        self,
        *,
        installation_repo: InstallationRepository,
        permissions_api: GitHubPermissionsAPI,
        get_jwt: object,
    ) -> None:
        self._repo = installation_repo
        self._permissions_api = permissions_api
        self._get_jwt = get_jwt  # callable: (installation) -> str

    def scan_all(self) -> list[DriftEvent]:
        drift_events: list[DriftEvent] = []

        for installation in self._repo.list_active():
            event = self._scan_one(installation)
            if event is not None:
                drift_events.append(event)

        return drift_events

    def _scan_one(self, installation: object) -> DriftEvent | None:
        try:
            jwt_token = self._get_jwt(installation)  # type: ignore[call-arg]
            raw = self._permissions_api.get_installation_permissions(
                github_installation_id=installation.github_installation_id,  # type: ignore[attr-defined]
                base_url=installation.github_base_url,  # type: ignore[attr-defined]
                jwt=jwt_token,
            )
            parsed = parse_github_permissions(raw)
            current_hash = hash_permissions(parsed)
            expected_hash: str = installation.permissions_hash  # type: ignore[attr-defined]

            if current_hash == expected_hash:
                return None

            logger.error(
                "github_permission_drift",
                extra={
                    "installation_id": installation.installation_id,  # type: ignore[attr-defined]
                    "tenant_id": installation.tenant_id,  # type: ignore[attr-defined]
                    "team_id": installation.team_id,  # type: ignore[attr-defined]
                    "previous_hash": expected_hash,
                    "current_hash": current_hash,
                },
            )
            self._repo.mark_drift(installation.installation_id)  # type: ignore[attr-defined]

            return DriftEvent(
                installation_id=installation.installation_id,  # type: ignore[attr-defined]
                tenant_id=installation.tenant_id,  # type: ignore[attr-defined]
                team_id=installation.team_id,  # type: ignore[attr-defined]
                previous_hash=expected_hash,
                current_hash=current_hash,
                current_permissions=parsed,
            )
        except Exception:
            logger.exception(
                "github_drift_scan_error",
                extra={"installation_id": getattr(installation, "installation_id", "unknown")},
            )
            return None
