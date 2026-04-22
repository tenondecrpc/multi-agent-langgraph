from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.persistence.testing.governance import InMemoryModelCatalog

DeploymentProfile = Literal["connected", "air_gapped"]
RuntimeRole = Literal["planner", "coder", "tester", "reviewer", "pr_creator"]


class TokenCap(BaseModel):
    input_tokens: int
    output_tokens: int


class ModelCatalogEntry(BaseModel):
    model_id: str
    provider_id: str
    deployment_profile: DeploymentProfile
    max_input_tokens: int
    max_output_tokens: int
    default_price_card_id: str
    supports_tools: bool = False
    supports_json_mode: bool = False
    supports_streaming: bool = False
    allowed_fallback_targets: list[str] = Field(default_factory=list)


class RoleTokenPolicy(BaseModel):
    role: RuntimeRole
    max_input_tokens: int
    max_output_tokens: int


__all__ = [
    "DeploymentProfile",
    "InMemoryModelCatalog",
    "ModelCatalogEntry",
    "RoleTokenPolicy",
    "RuntimeRole",
    "TokenCap",
]


def __getattr__(name: str):
    if name == "InMemoryModelCatalog":
        from backend.persistence.testing.governance import InMemoryModelCatalog

        return InMemoryModelCatalog
    raise AttributeError(name)
