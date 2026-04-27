from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum

from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field


class AuthRole(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"
    SUPER_ADMIN = "super-admin"


class AuthContext(BaseModel):
    subject_id: str
    tenant_id: str
    team_ids: list[str]
    role: AuthRole
    session_id: str
    expires_at: datetime
    break_glass_grants: list[str] = Field(default_factory=list)


class AuthorizationDecision(BaseModel):
    allowed: bool
    reason: str | None = None


ROLE_RANK = {
    AuthRole.VIEWER: 0,
    AuthRole.OPERATOR: 1,
    AuthRole.ADMIN: 2,
    AuthRole.SUPER_ADMIN: 3,
}


class OidcClaimMapper:
    def map_claims(self, raw_claims: Mapping[str, object]) -> AuthContext:
        subject_id = str(raw_claims["sub"])
        tenant_id = str(raw_claims["tenant_id"])
        team_ids = [str(team_id) for team_id in raw_claims.get("team_ids", [])]
        role_value = str(raw_claims.get("role", AuthRole.VIEWER.value))
        break_glass_grants = [str(item) for item in raw_claims.get("break_glass_grants", [])]
        expires_at = datetime.fromtimestamp(int(raw_claims["exp"]), tz=UTC)

        return AuthContext(
            subject_id=subject_id,
            tenant_id=tenant_id,
            team_ids=team_ids,
            role=AuthRole(role_value),
            session_id=str(raw_claims.get("sid", f"session-{subject_id}")),
            expires_at=expires_at,
            break_glass_grants=break_glass_grants,
        )


class AuthorizationPolicy:
    ACTION_REQUIREMENTS = {
        "view_runs": AuthRole.VIEWER,
        "operate_runs": AuthRole.OPERATOR,
        "manage_config": AuthRole.ADMIN,
        "manage_credentials": AuthRole.ADMIN,
        "cross_tenant_admin": AuthRole.SUPER_ADMIN,
    }

    def authorize(
        self,
        auth_context: AuthContext,
        *,
        action: str,
        tenant_id: str,
        team_id: str | None = None,
        cross_tenant: bool = False,
    ) -> AuthorizationDecision:
        if auth_context.expires_at <= datetime.now(tz=UTC):
            return AuthorizationDecision(allowed=False, reason="session_expired")

        required_role = self.ACTION_REQUIREMENTS[action]
        if ROLE_RANK[auth_context.role] < ROLE_RANK[required_role]:
            return AuthorizationDecision(allowed=False, reason="insufficient_role")

        if cross_tenant and auth_context.role is not AuthRole.SUPER_ADMIN:
            return AuthorizationDecision(allowed=False, reason="cross_tenant_requires_super_admin")

        if not cross_tenant and auth_context.tenant_id != tenant_id:
            return AuthorizationDecision(allowed=False, reason="tenant_scope_violation")

        if team_id is not None and auth_context.role is not AuthRole.SUPER_ADMIN:
            if team_id not in auth_context.team_ids:
                return AuthorizationDecision(allowed=False, reason="team_scope_violation")

        return AuthorizationDecision(allowed=True)


def require_role(minimum_role: AuthRole):
    def _get_auth_context(
        request: Request,
        x_tenant_id: str = Header(alias="X-Tenant-Id", default=""),
        x_team_id: str = Header(alias="X-Team-Id", default=""),
        x_role: str = Header(alias="X-Role", default="viewer"),
        x_subject: str = Header(alias="X-Subject", default=""),
        x_session: str = Header(alias="X-Session", default=""),
        x_expires: str = Header(alias="X-Expires", default=""),
    ) -> AuthContext:
        if not x_subject:
            raise HTTPException(status_code=401, detail="missing_subject")
        if not x_tenant_id:
            raise HTTPException(status_code=401, detail="missing_tenant")
        try:
            role = AuthRole(x_role)
        except ValueError:
            role = AuthRole.VIEWER
        try:
            expires_at = datetime.fromtimestamp(int(x_expires), tz=UTC)
        except (ValueError, TypeError):
            expires_at = datetime.now(tz=UTC)
        return AuthContext(
            subject_id=x_subject,
            tenant_id=x_tenant_id,
            team_ids=[x_team_id] if x_team_id else [],
            role=role,
            session_id=x_session,
            expires_at=expires_at,
        )

    def _check_role(auth_context: AuthContext = Depends(_get_auth_context)) -> AuthContext:  # noqa: B008
        if ROLE_RANK.get(auth_context.role, 0) < ROLE_RANK.get(minimum_role, 0):
            raise HTTPException(
                status_code=403,
                detail=f"insufficient_role: requires {minimum_role.value}, got {auth_context.role.value}",
            )
        return auth_context

    return _check_role
