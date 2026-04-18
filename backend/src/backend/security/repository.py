from __future__ import annotations

import re

from pydantic import BaseModel, Field

PROTECTED_PATH_MARKERS = (
    ".github/",
    "infra/",
    "helm/",
    "Dockerfile",
    "docker/",
    "CODEOWNERS",
    "secrets/",
)


class PlannedOrObservedDiff(BaseModel):
    changed_paths: list[str]
    diff_text_chunks: list[str] = Field(default_factory=list)
    branch_protected: bool = True
    signed_commits: bool = True


class RepositoryPolicyDecision(BaseModel):
    allowed: bool
    escalation_reason: str | None = None
    blocked_paths: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)


class RepositoryPolicy:
    SECRET_PATTERNS = [
        re.compile(r"ghp_[A-Za-z0-9]{20,}"),
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    ]

    def evaluate_diff(self, diff: PlannedOrObservedDiff) -> RepositoryPolicyDecision:
        blocked_paths = [
            path for path in diff.changed_paths if any(marker in path for marker in PROTECTED_PATH_MARKERS)
        ]
        findings = [
            "secret_scan_failed"
            for chunk in diff.diff_text_chunks
            if any(pattern.search(chunk) for pattern in self.SECRET_PATTERNS)
        ]

        if blocked_paths:
            return RepositoryPolicyDecision(
                allowed=False,
                escalation_reason="security_review",
                blocked_paths=blocked_paths,
            )

        if findings:
            return RepositoryPolicyDecision(
                allowed=False,
                escalation_reason="secret_scan_failed",
                findings=findings,
            )

        if not diff.branch_protected:
            return RepositoryPolicyDecision(
                allowed=False,
                escalation_reason="missing_branch_protection",
            )

        if not diff.signed_commits:
            return RepositoryPolicyDecision(
                allowed=False,
                escalation_reason="unsigned_commit",
            )

        return RepositoryPolicyDecision(allowed=True)
