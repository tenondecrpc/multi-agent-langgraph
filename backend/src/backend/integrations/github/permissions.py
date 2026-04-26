from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

logger = logging.getLogger(__name__)


class GitHubPermission(StrEnum):
    CONTENTS_READ = "contents:read"
    CONTENTS_WRITE = "contents:write"
    PULL_REQUESTS_WRITE = "pull_requests:write"
    CHECKS_WRITE = "checks:write"
    METADATA_READ = "metadata:read"
    STATUSES_READ = "statuses:read"
    ADMINISTRATION_READ = "administration:read"


# Least-privilege set per documented operation. Any call outside this set fails closed.
OPERATION_PERMISSIONS: dict[str, frozenset[GitHubPermission]] = {
    "create_pull_request": frozenset({
        GitHubPermission.CONTENTS_READ,
        GitHubPermission.PULL_REQUESTS_WRITE,
        GitHubPermission.METADATA_READ,
    }),
    "push_branch": frozenset({
        GitHubPermission.CONTENTS_WRITE,
        GitHubPermission.METADATA_READ,
    }),
    "get_branch_protection": frozenset({
        GitHubPermission.ADMINISTRATION_READ,
        GitHubPermission.METADATA_READ,
    }),
    "create_check_run": frozenset({
        GitHubPermission.CHECKS_WRITE,
        GitHubPermission.METADATA_READ,
    }),
    "get_commit_status": frozenset({
        GitHubPermission.STATUSES_READ,
        GitHubPermission.METADATA_READ,
    }),
}

MINIMUM_REQUIRED_PERMISSIONS: frozenset[GitHubPermission] = frozenset({
    GitHubPermission.CONTENTS_READ,
    GitHubPermission.PULL_REQUESTS_WRITE,
    GitHubPermission.METADATA_READ,
    GitHubPermission.ADMINISTRATION_READ,
    GitHubPermission.CONTENTS_WRITE,
})


@dataclass(frozen=True)
class PermissionCheckResult:
    allowed: bool
    operation: str
    missing: list[str]
    reason: str | None = None


def hash_permissions(permissions: dict[str, str]) -> str:
    canonical = json.dumps(permissions, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def check_operation_permission(
    operation: str,
    granted_permissions: dict[str, str],
) -> PermissionCheckResult:
    required = OPERATION_PERMISSIONS.get(operation)
    if required is None:
        logger.warning("unknown_github_operation", extra={"operation": operation})
        return PermissionCheckResult(
            allowed=False,
            operation=operation,
            missing=[],
            reason="unknown_operation",
        )

    valid_values = {p.value for p in GitHubPermission}
    granted_set = {
        GitHubPermission(f"{k}:{v}")
        for k, v in granted_permissions.items()
        if f"{k}:{v}" in valid_values
    }
    missing = sorted(p.value for p in required if p not in granted_set)

    if missing:
        logger.warning(
            "github_permission_missing",
            extra={"operation": operation, "missing": missing},
        )
        return PermissionCheckResult(allowed=False, operation=operation, missing=missing, reason="missing_permissions")

    return PermissionCheckResult(allowed=True, operation=operation, missing=[])


def parse_github_permissions(raw: dict[str, Literal["read", "write", "none"]]) -> dict[str, str]:
    return {k: v for k, v in raw.items() if v != "none"}
