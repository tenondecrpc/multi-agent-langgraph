from __future__ import annotations

from pydantic import BaseModel, Field

from backend.governance.catalog import DeploymentProfile, RuntimeRole
from backend.persistence.contracts import ModelCatalog

RUNTIME_ROLE_TOOL_ALLOWLIST: dict[RuntimeRole, set[str]] = {
    "planner": {
        "jira_read",
        "repo_read",
        "checkpoint_read",
        "memory_read",
        "first_party_lookup",
        "bounded_research",
    },
    "coder": {"repo_write", "local_test", "build_tool"},
    "tester": {"test_run", "static_analysis", "artifact_read", "sandbox_control"},
    "reviewer": {"repo_read", "diff_analysis", "policy_check", "first_party_lookup"},
    "pr_creator": {"git_metadata", "pr_create", "jira_write", "final_policy_check"},
}


class AgentConfigVersion(BaseModel):
    agent_role: RuntimeRole
    model_id: str
    fallback_model_id: str | None = None
    system_prompt_ref: str
    allowed_tools: list[str] = Field(default_factory=list)
    retry_limits: dict[str, int] = Field(default_factory=dict)
    token_policy_ref: str


class AgentValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class AgentDryRunResult(BaseModel):
    allowed: bool
    blocked_tools: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AgentConfigValidator:
    def __init__(
        self,
        *,
        model_catalog: ModelCatalog,
        deployment_profile: DeploymentProfile,
    ) -> None:
        self.model_catalog = model_catalog
        self.deployment_profile = deployment_profile

    def validate(self, config: AgentConfigVersion) -> AgentValidationResult:
        errors: list[str] = []

        try:
            self.model_catalog.resolve_model(config.model_id, self.deployment_profile)
        except ValueError as exc:
            errors.append(str(exc))

        if config.fallback_model_id is not None:
            try:
                self.model_catalog.validate_fallback(
                    primary_model_id=config.model_id,
                    fallback_model_id=config.fallback_model_id,
                    deployment_profile=self.deployment_profile,
                )
            except ValueError as exc:
                errors.append(str(exc))

        allowed_tools = RUNTIME_ROLE_TOOL_ALLOWLIST[config.agent_role]
        invalid_tools = sorted(set(config.allowed_tools) - allowed_tools)
        if invalid_tools:
            errors.append(
                f"Role `{config.agent_role}` cannot grant tools: {', '.join(invalid_tools)}."
            )

        if not config.system_prompt_ref:
            errors.append("System prompt reference is required.")
        if not config.retry_limits:
            errors.append("Retry limits are required.")
        if any(limit < 0 for limit in config.retry_limits.values()):
            errors.append("Retry limits must be non-negative.")
        if not config.token_policy_ref:
            errors.append("Token policy reference is required.")

        return AgentValidationResult(valid=not errors, errors=errors)

    def dry_run(
        self,
        config: AgentConfigVersion,
        *,
        requested_tools: list[str],
    ) -> AgentDryRunResult:
        validation = self.validate(config)
        if not validation.valid:
            return AgentDryRunResult(allowed=False, errors=validation.errors)

        blocked_tools = sorted(set(requested_tools) - set(config.allowed_tools))
        return AgentDryRunResult(
            allowed=not blocked_tools,
            blocked_tools=blocked_tools,
        )


def default_agent_configs(
    model_mapping: dict[RuntimeRole, str] | None = None,
) -> list[AgentConfigVersion]:
    defaults = model_mapping or {
        "planner": "gpt-4.1",
        "coder": "gpt-4.1",
        "tester": "llama3.1",
        "reviewer": "gpt-4.1",
        "pr_creator": "gpt-4.1",
    }
    retry_limits = {
        "planner": {"clarification": 2},
        "coder": {"implementation": 2},
        "tester": {"tests": 2},
        "reviewer": {"review": 1},
        "pr_creator": {"pre_pr": 1},
    }
    return [
        AgentConfigVersion(
            agent_role=role,
            model_id=model_id,
            system_prompt_ref=f"prompts/{role}.txt",
            allowed_tools=sorted(RUNTIME_ROLE_TOOL_ALLOWLIST[role]),
            retry_limits=retry_limits[role],
            token_policy_ref=f"token-policy/{role}",
        )
        for role, model_id in defaults.items()
    ]
