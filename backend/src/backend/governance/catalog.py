from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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


class InMemoryModelCatalog:
    def __init__(
        self,
        *,
        entries: list[ModelCatalogEntry],
        role_token_policies: list[RoleTokenPolicy],
    ) -> None:
        self._entries = {
            (entry.model_id, entry.deployment_profile): entry for entry in entries
        }
        self._role_token_policies = {
            policy.role: policy for policy in role_token_policies
        }

    def resolve_model(
        self,
        model_id: str,
        deployment_profile: DeploymentProfile,
    ) -> ModelCatalogEntry:
        try:
            return self._entries[(model_id, deployment_profile)]
        except KeyError as exc:
            raise ValueError(
                f"Unknown model `{model_id}` for deployment profile `{deployment_profile}`."
            ) from exc

    def validate_fallback(
        self,
        *,
        primary_model_id: str,
        fallback_model_id: str,
        deployment_profile: DeploymentProfile,
    ) -> None:
        primary = self.resolve_model(primary_model_id, deployment_profile)
        self.resolve_model(fallback_model_id, deployment_profile)
        if fallback_model_id not in primary.allowed_fallback_targets:
            raise ValueError(
                f"Model `{fallback_model_id}` is not an allowed fallback for `{primary_model_id}`."
            )

    def effective_token_cap(
        self,
        *,
        role: RuntimeRole,
        model_id: str,
        deployment_profile: DeploymentProfile,
        tenant_override: TokenCap | None = None,
    ) -> TokenCap:
        entry = self.resolve_model(model_id, deployment_profile)
        role_policy = self._role_token_policies[role]
        input_limit = min(entry.max_input_tokens, role_policy.max_input_tokens)
        output_limit = min(entry.max_output_tokens, role_policy.max_output_tokens)

        if tenant_override is not None:
            input_limit = min(input_limit, tenant_override.input_tokens)
            output_limit = min(output_limit, tenant_override.output_tokens)

        return TokenCap(
            input_tokens=input_limit,
            output_tokens=output_limit,
        )
