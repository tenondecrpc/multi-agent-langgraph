from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

_TOKEN_TTL_SECONDS = 3600  # GitHub installation tokens are valid for 1 hour max


@dataclass(frozen=True)
class InstallationToken:
    token: str
    expires_at_epoch: float
    installation_id: str
    tenant_id: str
    team_id: str


class VaultClient(Protocol):
    def read_secret(self, path: str) -> str: ...


class GitHubAPIClient(Protocol):
    def create_installation_token(
        self,
        *,
        github_installation_id: int,
        jwt: str,
        base_url: str,
    ) -> dict[str, str]: ...


class InstallationRecord(Protocol):
    installation_id: str
    tenant_id: str
    team_id: str
    github_installation_id: int
    github_base_url: str
    drift_acknowledged: bool


class MintingError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InstallationTokenMinter:
    """Mints short-lived GitHub App installation tokens using a Vault-held private key.

    Tokens are never persisted - they are returned to the caller for single-request use.
    """

    def __init__(
        self,
        *,
        vault_client: VaultClient,
        github_api: GitHubAPIClient,
        app_id: str,
        vault_private_key_path: str,
    ) -> None:
        self._vault = vault_client
        self._github = github_api
        self._app_id = app_id
        self._vault_private_key_path = vault_private_key_path

    def mint(self, record: InstallationRecord) -> InstallationToken:
        if not record.drift_acknowledged:
            logger.error(
                "github_mint_blocked_drift",
                extra={"installation_id": record.installation_id, "tenant_id": record.tenant_id},
            )
            raise MintingError("permission_drift_unacknowledged")

        private_key_pem = self._vault.read_secret(self._vault_private_key_path)
        jwt_token = _build_app_jwt(private_key_pem=private_key_pem, app_id=self._app_id)

        logger.info(
            "github_mint_attempt",
            extra={
                "installation_id": record.installation_id,
                "tenant_id": record.tenant_id,
                "team_id": record.team_id,
            },
        )

        response = self._github.create_installation_token(
            github_installation_id=record.github_installation_id,
            jwt=jwt_token,
            base_url=record.github_base_url,
        )

        token = response.get("token", "")
        if not token:
            raise MintingError("empty_token_from_github")

        expires_at = time.time() + _TOKEN_TTL_SECONDS
        logger.info(
            "github_mint_success",
            extra={
                "installation_id": record.installation_id,
                "tenant_id": record.tenant_id,
                "team_id": record.team_id,
            },
        )
        return InstallationToken(
            token=token,
            expires_at_epoch=expires_at,
            installation_id=record.installation_id,
            tenant_id=record.tenant_id,
            team_id=record.team_id,
        )


def _build_app_jwt(*, private_key_pem: str, app_id: str) -> str:
    """Build a GitHub App JWT. Requires PyJWT and cryptography packages."""
    try:
        import jwt
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        now = int(time.time())
        private_key = load_pem_private_key(private_key_pem.encode(), password=None)
        payload = {"iat": now - 60, "exp": now + 540, "iss": app_id}
        return jwt.encode(payload, private_key, algorithm="RS256")
    except ImportError as exc:
        raise MintingError("jwt_dependency_missing") from exc
