from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class InstallationWizardRequest(BaseModel):
    tenant_id: str
    team_id: str
    account_login: str
    github_installation_id: int
    permissions: dict[str, str]
    github_base_url: str = "https://api.github.com"


class InstallationWizardResponse(BaseModel):
    installation_id: str
    tenant_id: str
    team_id: str
    account_login: str
    permissions_hash: str


class PATOptInRequest(BaseModel):
    tenant_id: str
    team_id: str
    rationale: str
    allowed_scopes: list[str]
    expires_at: datetime


class PATOptInResponse(BaseModel):
    opt_in_id: str
    tenant_id: str
    team_id: str
    expires_at: datetime
    pat_mode_active: bool = True


class PATModeStatus(BaseModel):
    tenant_id: str
    team_id: str
    pat_mode_active: bool
    expires_at: datetime | None
    allowed_scopes: list[str]


def build_github_router() -> APIRouter:
    from backend.integrations.github.permissions import hash_permissions, parse_github_permissions

    router = APIRouter(prefix="/api/v1/admin/github", tags=["github"])

    @router.post("/installations", response_model=InstallationWizardResponse, status_code=status.HTTP_201_CREATED)
    async def register_installation(
        body: InstallationWizardRequest,
        x_actor: Annotated[str, Header(alias="X-Actor")],
    ) -> InstallationWizardResponse:
        parsed = parse_github_permissions(body.permissions)
        p_hash = hash_permissions(parsed)
        installation_id = str(uuid.uuid4())

        logger.info(
            "github_app_installed",
            extra={
                "installation_id": installation_id,
                "tenant_id": body.tenant_id,
                "team_id": body.team_id,
                "actor": x_actor,
                "account_login": body.account_login,
            },
        )

        return InstallationWizardResponse(
            installation_id=installation_id,
            tenant_id=body.tenant_id,
            team_id=body.team_id,
            account_login=body.account_login,
            permissions_hash=p_hash,
        )

    @router.delete("/installations/{installation_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def revoke_installation(
        installation_id: str,
        x_actor: Annotated[str, Header(alias="X-Actor")],
    ) -> None:
        logger.info(
            "github_app_uninstalled",
            extra={"installation_id": installation_id, "actor": x_actor},
        )

    @router.post("/pat-opt-ins", response_model=PATOptInResponse, status_code=status.HTTP_201_CREATED)
    async def create_pat_opt_in(
        body: PATOptInRequest,
        x_actor: Annotated[str, Header(alias="X-Actor")],
        x_role: Annotated[str, Header(alias="X-Role")],
    ) -> PATOptInResponse:
        if x_role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="pat_opt_in_requires_super_admin",
            )
        if body.expires_at <= datetime.now(tz=UTC):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="expires_at_must_be_in_future",
            )

        opt_in_id = str(uuid.uuid4())
        logger.info(
            "github_pat_opt_in_created",
            extra={
                "opt_in_id": opt_in_id,
                "tenant_id": body.tenant_id,
                "team_id": body.team_id,
                "actor": x_actor,
                "allowed_scopes": body.allowed_scopes,
                "expires_at": body.expires_at.isoformat(),
            },
        )

        return PATOptInResponse(
            opt_in_id=opt_in_id,
            tenant_id=body.tenant_id,
            team_id=body.team_id,
            expires_at=body.expires_at,
        )

    @router.get("/pat-opt-ins/{tenant_id}/{team_id}", response_model=PATModeStatus)
    async def get_pat_mode_status(
        tenant_id: str,
        team_id: str,
    ) -> PATModeStatus:
        # In production this queries pat_opt_ins table via the repository.
        # Returns a stub indicating no active PAT opt-in for the given tenant/team.
        return PATModeStatus(
            tenant_id=tenant_id,
            team_id=team_id,
            pat_mode_active=False,
            expires_at=None,
            allowed_scopes=[],
        )

    @router.post("/installations/{installation_id}/acknowledge-drift", status_code=status.HTTP_200_OK)
    async def acknowledge_drift(
        installation_id: str,
        x_actor: Annotated[str, Header(alias="X-Actor")],
        x_role: Annotated[str, Header(alias="X-Role")],
    ) -> dict[str, str]:
        if x_role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="drift_acknowledgement_requires_super_admin",
            )
        logger.info(
            "github_drift_acknowledged",
            extra={"installation_id": installation_id, "actor": x_actor},
        )
        return {"status": "acknowledged", "installation_id": installation_id}

    return router
