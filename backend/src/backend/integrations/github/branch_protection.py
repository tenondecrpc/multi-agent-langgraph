from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)

_ENFORCE_ENV_VAR = "GITHUB_BRANCH_PROTECTION_ENFORCE"


def is_enforce_mode() -> bool:
    """Return True when the branch-protection kill switch is flipped to enforce.

    Default is shadow mode (logs but does not block). Set
    GITHUB_BRANCH_PROTECTION_ENFORCE=true to enable enforcement.
    """
    return os.getenv(_ENFORCE_ENV_VAR, "").lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class BranchProtectionConfig:
    required_status_checks: list[str]
    require_review: bool
    require_signed_commits: bool
    require_linear_history: bool


@dataclass
class BranchProtectionResult:
    passed: bool
    missing: list[str] = field(default_factory=list)
    shadow_mode: bool = True
    repo_full_name: str = ""
    branch: str = ""
    evidence: str = ""


class GitHubBranchProtectionAPI(Protocol):
    def get_branch_protection(
        self,
        *,
        repo_full_name: str,
        branch: str,
        token: str,
        base_url: str,
    ) -> dict[str, object]: ...


class BranchProtectionVerifier:
    """Verifies branch-protection settings before PR creation.

    Operates in two modes:
    - shadow_mode=True (default): logs failures but does not block PR creation.
    - shadow_mode=False (enforce): missing protections block PR creation and escalate.

    The mode is controlled by the GITHUB_BRANCH_PROTECTION_ENFORCE feature flag.
    """

    def __init__(
        self,
        *,
        api: GitHubBranchProtectionAPI,
        shadow_mode: bool = True,
    ) -> None:
        self._api = api
        self._shadow_mode = shadow_mode

    @property
    def shadow_mode(self) -> bool:
        return self._shadow_mode

    def verify(
        self,
        *,
        repo_full_name: str,
        branch: str,
        token: str,
        base_url: str,
        required_config: BranchProtectionConfig,
    ) -> BranchProtectionResult:
        missing: list[str] = []
        try:
            raw = self._api.get_branch_protection(
                repo_full_name=repo_full_name,
                branch=branch,
                token=token,
                base_url=base_url,
            )
            missing = _find_missing_protections(raw, required_config)
        except Exception:
            logger.exception(
                "github_branch_protection_fetch_error",
                extra={"repo": repo_full_name, "branch": branch},
            )
            missing = ["protection_fetch_failed"]

        passed = len(missing) == 0
        evidence = _build_evidence(missing, shadow_mode=self._shadow_mode)

        if not passed:
            logger.warning(
                "github_branch_protection_missing",
                extra={
                    "repo": repo_full_name,
                    "branch": branch,
                    "missing": missing,
                    "shadow_mode": self._shadow_mode,
                    "blocked": not self._shadow_mode,
                },
            )

        return BranchProtectionResult(
            passed=passed,
            missing=missing,
            shadow_mode=self._shadow_mode,
            repo_full_name=repo_full_name,
            branch=branch,
            evidence=evidence,
        )


def _find_missing_protections(
    raw: dict[str, object],
    config: BranchProtectionConfig,
) -> list[str]:
    missing: list[str] = []

    if config.require_review:
        reviews = raw.get("required_pull_request_reviews")
        if not reviews:
            missing.append("required_pull_request_reviews")

    if config.require_signed_commits:
        signed = raw.get("required_signatures", {})
        if not (isinstance(signed, dict) and signed.get("enabled")):
            missing.append("required_signatures")

    if config.require_linear_history:
        linear = raw.get("required_linear_history", {})
        if not (isinstance(linear, dict) and linear.get("enabled")):
            missing.append("required_linear_history")

    if config.required_status_checks:
        checks = raw.get("required_status_checks", {})
        configured: list[str] = []
        if isinstance(checks, dict):
            contexts = checks.get("contexts", [])
            if isinstance(contexts, list):
                configured = list(contexts)
        for check in config.required_status_checks:
            if check not in configured:
                missing.append(f"required_status_check:{check}")

    return missing


def _build_evidence(missing: list[str], *, shadow_mode: bool) -> str:
    if not missing:
        return "all_required_protections_present"
    mode = "shadow_logged" if shadow_mode else "blocked"
    return f"missing_protections={','.join(missing)}; mode={mode}"


class _NullBranchProtectionAPI:
    """Stub used when no real GitHub client is configured (e.g. in tests)."""

    def get_branch_protection(
        self,
        *,
        repo_full_name: str,
        branch: str,
        token: str,
        base_url: str,
    ) -> dict[str, object]:
        return {}
