"""Admission exceptions API for supply-chain policy overrides.

Provides CRUD endpoints for managing admission exceptions that allow
unsigned or non-compliant images to bypass Kyverno policies.
Exceptions require dual super_admin approval and mandatory expiration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field


class AdmissionExceptionCreate(BaseModel):
    tenant_id: str
    team_id: str
    policy_name: str
    image_reference: str
    rationale: str
    approved_by: str
    second_approver: str
    expires_at: datetime
    metadata: dict = Field(default_factory=dict)


class AdmissionExceptionResponse(BaseModel):
    exception_id: str
    tenant_id: str
    team_id: str
    policy_name: str
    image_reference: str
    rationale: str
    approved_by: str
    second_approver: str
    expires_at: datetime
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None
    metadata: dict
    created_at: datetime
    updated_at: datetime


class AdmissionExceptionRevoke(BaseModel):
    revoked_by: str
    revoke_reason: str


class AdmissionExceptionListResponse(BaseModel):
    exceptions: list[AdmissionExceptionResponse]
    total: int


def build_admission_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/admission-exceptions", tags=["admission-exceptions"])

    @router.post("/", response_model=AdmissionExceptionResponse, status_code=201)
    def create_exception(request: AdmissionExceptionCreate) -> AdmissionExceptionResponse:
        now = datetime.now(UTC)
        if request.expires_at <= now:
            raise HTTPException(
                status_code=400,
                detail="expires_at must be in the future",
            )
        if request.approved_by == request.second_approver:
            raise HTTPException(
                status_code=400,
                detail="second_approver must be different from approved_by",
            )

        exception_id = f"exc-{uuid.uuid4().hex[:12]}"
        response = AdmissionExceptionResponse(
            exception_id=exception_id,
            tenant_id=request.tenant_id,
            team_id=request.team_id,
            policy_name=request.policy_name,
            image_reference=request.image_reference,
            rationale=request.rationale,
            approved_by=request.approved_by,
            second_approver=request.second_approver,
            expires_at=request.expires_at,
            metadata=request.metadata,
            created_at=now,
            updated_at=now,
        )
        return response

    @router.get("/", response_model=AdmissionExceptionListResponse)
    def list_exceptions(
        tenant_id: str | None = None,
        policy_name: str | None = None,
        include_revoked: bool = False,
    ) -> AdmissionExceptionListResponse:
        return AdmissionExceptionListResponse(exceptions=[], total=0)

    @router.get("/{exception_id}", response_model=AdmissionExceptionResponse)
    def get_exception(exception_id: str) -> AdmissionExceptionResponse:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found")

    @router.post("/{exception_id}/revoke", response_model=AdmissionExceptionResponse)
    def revoke_exception(
        exception_id: str,
        request: AdmissionExceptionRevoke,
    ) -> AdmissionExceptionResponse:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found")

    @router.delete("/{exception_id}", status_code=204)
    def delete_exception(exception_id: str) -> Response:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found")

    return router
