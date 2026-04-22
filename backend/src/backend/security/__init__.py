from __future__ import annotations

from importlib import import_module

__all__ = [
    "AuthContext",
    "AuthRole",
    "AuthorizationDecision",
    "AuthorizationPolicy",
    "CredentialPolicy",
    "CredentialPolicyDecision",
    "CredentialRecord",
    "InMemoryWebhookGuard",
    "OidcClaimMapper",
    "PlannedOrObservedDiff",
    "PromptEnvelope",
    "PromptSafetyDecision",
    "PromptSafetyService",
    "RepositoryPolicy",
    "RepositoryPolicyDecision",
    "ToolPolicyDecision",
    "ToolPolicyEnforcer",
    "WebhookGuardResult",
    "WebhookRequest",
]

_EXPORTS = {
    "AuthContext": (".auth", "AuthContext"),
    "AuthRole": (".auth", "AuthRole"),
    "AuthorizationDecision": (".auth", "AuthorizationDecision"),
    "AuthorizationPolicy": (".auth", "AuthorizationPolicy"),
    "CredentialPolicy": (".credentials", "CredentialPolicy"),
    "CredentialPolicyDecision": (".credentials", "CredentialPolicyDecision"),
    "CredentialRecord": (".credentials", "CredentialRecord"),
    "InMemoryWebhookGuard": (".webhook", "InMemoryWebhookGuard"),
    "OidcClaimMapper": (".auth", "OidcClaimMapper"),
    "PlannedOrObservedDiff": (".repository", "PlannedOrObservedDiff"),
    "PromptEnvelope": (".prompt", "PromptEnvelope"),
    "PromptSafetyDecision": (".prompt", "PromptSafetyDecision"),
    "PromptSafetyService": (".prompt", "PromptSafetyService"),
    "RepositoryPolicy": (".repository", "RepositoryPolicy"),
    "RepositoryPolicyDecision": (".repository", "RepositoryPolicyDecision"),
    "ToolPolicyDecision": (".prompt", "ToolPolicyDecision"),
    "ToolPolicyEnforcer": (".prompt", "ToolPolicyEnforcer"),
    "WebhookGuardResult": (".webhook", "WebhookGuardResult"),
    "WebhookRequest": (".webhook", "WebhookRequest"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name, __name__)
    return getattr(module, attr_name)
