from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel

# GitHub App integration gets the full rate limit budget.
# PAT mode is halved per the constitution (stricter per-tenant limits).
GITHUB_APP_RATE_LIMIT_PER_HOUR = 5000
GITHUB_PAT_RATE_LIMIT_PER_HOUR = 2500


class CredentialRecord(BaseModel):
    tenant_id: str
    team_id: str
    provider: str
    credential_type: Literal["github_app", "pat"]
    encrypted_payload: str
    rotated_at: datetime
    rotation_window_days: int = 90


class CredentialPolicyDecision(BaseModel):
    allowed: bool
    reason: str | None = None
    rate_limit_per_hour: int | None = None


class PATOptInRecord(BaseModel):
    opt_in_id: str
    tenant_id: str
    team_id: str
    approver_actor: str
    rationale: str
    allowed_scopes: list[str]
    expires_at: datetime


class CredentialPolicy:
    def validate(
        self,
        record: CredentialRecord,
        *,
        now: datetime | None = None,
        pat_opt_in: PATOptInRecord | None = None,
    ) -> CredentialPolicyDecision:
        evaluation_time = now or datetime.now(tz=UTC)
        rotation_deadline = record.rotated_at + timedelta(days=record.rotation_window_days)

        if evaluation_time > rotation_deadline:
            return CredentialPolicyDecision(allowed=False, reason="rotation_overdue")

        if record.provider == "github" and record.credential_type == "pat":
            if pat_opt_in is None:
                return CredentialPolicyDecision(allowed=False, reason="pat_requires_explicit_opt_in")
            if evaluation_time > pat_opt_in.expires_at:
                return CredentialPolicyDecision(allowed=False, reason="pat_opt_in_expired")
            return CredentialPolicyDecision(
                allowed=True,
                rate_limit_per_hour=GITHUB_PAT_RATE_LIMIT_PER_HOUR,
            )

        rate_limit = GITHUB_APP_RATE_LIMIT_PER_HOUR if record.provider == "github" else None
        return CredentialPolicyDecision(allowed=True, rate_limit_per_hour=rate_limit)
