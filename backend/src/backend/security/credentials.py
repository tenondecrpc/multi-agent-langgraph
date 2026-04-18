from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel


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


class CredentialPolicy:
    def validate(self, record: CredentialRecord, *, now: datetime | None = None) -> CredentialPolicyDecision:
        evaluation_time = now or datetime.now(tz=UTC)
        rotation_deadline = record.rotated_at + timedelta(days=record.rotation_window_days)

        if evaluation_time > rotation_deadline:
            return CredentialPolicyDecision(allowed=False, reason="rotation_overdue")

        if record.provider == "github" and record.credential_type == "pat":
            return CredentialPolicyDecision(allowed=False, reason="pat_requires_explicit_opt_in")

        return CredentialPolicyDecision(allowed=True)
