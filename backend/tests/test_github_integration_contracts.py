"""Contract tests for GitHub App and PAT onboarding mechanics.

These tests cover:
- Permission hash and operation-permission enforcement
- Installation token minting (happy path, drift block, JWT error)
- Permission drift detection
- Branch protection verification (shadow and enforce modes)
- CredentialPolicy PAT opt-in and rate-limit logic
- EscalationReason.BRANCH_PROTECTION_MISSING in the workflow
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from backend.integrations.github.branch_protection import (
    BranchProtectionConfig,
    BranchProtectionVerifier,
    _NullBranchProtectionAPI,
    is_enforce_mode,
)
from backend.integrations.github.drift import PermissionDriftScanner
from backend.integrations.github.minting import (
    InstallationToken,
    InstallationTokenMinter,
    MintingError,
)
from backend.integrations.github.permissions import (
    check_operation_permission,
    hash_permissions,
    parse_github_permissions,
)
from backend.runtime.models import (
    EscalationReason,
    PlanningRequest,
    TicketRunState,
)
from backend.security.credentials import (
    GITHUB_APP_RATE_LIMIT_PER_HOUR,
    GITHUB_PAT_RATE_LIMIT_PER_HOUR,
    CredentialPolicy,
    CredentialRecord,
    PATOptInRecord,
)

# ---------------------------------------------------------------------------
# Permission hashing and operation enforcement
# ---------------------------------------------------------------------------


def test_hash_permissions_is_deterministic() -> None:
    perms = {"contents": "read", "pull_requests": "write"}
    assert hash_permissions(perms) == hash_permissions(perms)


def test_hash_permissions_differs_on_change() -> None:
    a = hash_permissions({"contents": "read"})
    b = hash_permissions({"contents": "write"})
    assert a != b


def test_parse_github_permissions_drops_none() -> None:
    raw = {"contents": "read", "issues": "none", "pull_requests": "write"}
    result = parse_github_permissions(raw)
    assert "issues" not in result
    assert result["contents"] == "read"
    assert result["pull_requests"] == "write"


def test_check_operation_permission_allowed() -> None:
    granted = {"contents": "read", "pull_requests": "write", "metadata": "read"}
    result = check_operation_permission("create_pull_request", granted)
    assert result.allowed is True
    assert result.missing == []


def test_check_operation_permission_blocked_on_missing() -> None:
    granted = {"contents": "read"}
    result = check_operation_permission("create_pull_request", granted)
    assert result.allowed is False
    assert len(result.missing) > 0
    assert result.reason == "missing_permissions"


def test_check_operation_permission_unknown_operation() -> None:
    result = check_operation_permission("do_something_weird", {"contents": "read"})
    assert result.allowed is False
    assert result.reason == "unknown_operation"


# ---------------------------------------------------------------------------
# Installation token minting
# ---------------------------------------------------------------------------


@dataclass
class _FakeInstallation:
    installation_id: str = "inst-1"
    tenant_id: str = "tenant-alpha"
    team_id: str = "team-core"
    github_installation_id: int = 12345
    github_base_url: str = "https://api.github.com"
    drift_acknowledged: bool = True


class _FakeVault:
    def read_secret(self, path: str) -> str:
        return "fake-private-key-pem"


class _FakeGitHubAPI:
    def create_installation_token(
        self,
        *,
        github_installation_id: int,
        jwt: str,
        base_url: str,
    ) -> dict[str, str]:
        return {"token": "ghs_test_token_abc123"}


def _make_minter(github_api=None) -> InstallationTokenMinter:
    return InstallationTokenMinter(
        vault_client=_FakeVault(),
        github_api=github_api or _FakeGitHubAPI(),
        app_id="app-999",
        vault_private_key_path="secret/github/app-key",
    )


def test_minting_blocked_when_drift_unacknowledged() -> None:
    minter = _make_minter()
    installation = _FakeInstallation(drift_acknowledged=False)
    with pytest.raises(MintingError) as exc_info:
        minter.mint(installation)
    assert exc_info.value.reason == "permission_drift_unacknowledged"


def test_minting_raises_when_github_returns_empty_token() -> None:
    class _EmptyTokenAPI:
        def create_installation_token(self, *, github_installation_id, jwt, base_url):
            return {"token": ""}

    minter = _make_minter(github_api=_EmptyTokenAPI())
    with patch(
        "backend.integrations.github.minting._build_app_jwt",
        return_value="fake-jwt",
    ):
        with pytest.raises(MintingError) as exc_info:
            minter.mint(_FakeInstallation())
    assert exc_info.value.reason == "empty_token_from_github"


def test_minting_raises_when_jwt_deps_missing() -> None:
    minter = _make_minter()
    with patch(
        "backend.integrations.github.minting._build_app_jwt",
        side_effect=MintingError("jwt_dependency_missing"),
    ):
        with pytest.raises(MintingError) as exc_info:
            minter.mint(_FakeInstallation())
    assert exc_info.value.reason == "jwt_dependency_missing"


def test_minting_success_token_not_persisted() -> None:
    minter = _make_minter()
    with patch(
        "backend.integrations.github.minting._build_app_jwt",
        return_value="fake-jwt",
    ):
        token = minter.mint(_FakeInstallation())
    assert isinstance(token, InstallationToken)
    assert token.token == "ghs_test_token_abc123"
    assert token.tenant_id == "tenant-alpha"
    assert token.team_id == "team-core"


# ---------------------------------------------------------------------------
# Permission drift detection
# ---------------------------------------------------------------------------


class _FakeInstallationRepo:
    def __init__(self, installations: list) -> None:
        self._installations = installations
        self.marked_drift: list[str] = []

    def list_active(self) -> list:
        return self._installations

    def mark_drift(self, installation_id: str) -> None:
        self.marked_drift.append(installation_id)

    def acknowledge_drift(self, installation_id: str, *, actor: str) -> None:
        pass


class _FakePermissionsAPI:
    def __init__(self, current_permissions: dict[str, str]) -> None:
        self._perms = current_permissions

    def get_installation_permissions(self, *, github_installation_id, base_url, jwt):
        return self._perms


@dataclass
class _FakeInstallationForDrift:
    installation_id: str
    tenant_id: str
    team_id: str
    github_installation_id: int
    github_base_url: str
    permissions_hash: str


def test_drift_scanner_no_drift_when_hash_unchanged() -> None:
    perms = {"contents": "read", "pull_requests": "write"}
    current_hash = hash_permissions(parse_github_permissions(perms))
    installation = _FakeInstallationForDrift(
        installation_id="inst-1",
        tenant_id="t1",
        team_id="tm1",
        github_installation_id=1,
        github_base_url="https://api.github.com",
        permissions_hash=current_hash,
    )
    repo = _FakeInstallationRepo([installation])
    scanner = PermissionDriftScanner(
        installation_repo=repo,
        permissions_api=_FakePermissionsAPI(perms),
        get_jwt=lambda _inst: "fake-jwt",
    )
    events = scanner.scan_all()
    assert events == []
    assert repo.marked_drift == []


def test_drift_scanner_emits_event_and_marks_when_hash_differs() -> None:
    original_perms = {"contents": "read"}
    drifted_perms = {"contents": "write", "administration": "read"}
    original_hash = hash_permissions(parse_github_permissions(original_perms))

    installation = _FakeInstallationForDrift(
        installation_id="inst-2",
        tenant_id="t1",
        team_id="tm1",
        github_installation_id=2,
        github_base_url="https://api.github.com",
        permissions_hash=original_hash,
    )
    repo = _FakeInstallationRepo([installation])
    scanner = PermissionDriftScanner(
        installation_repo=repo,
        permissions_api=_FakePermissionsAPI(drifted_perms),
        get_jwt=lambda _inst: "fake-jwt",
    )
    events = scanner.scan_all()
    assert len(events) == 1
    assert events[0].installation_id == "inst-2"
    assert "inst-2" in repo.marked_drift


# ---------------------------------------------------------------------------
# Branch protection verification
# ---------------------------------------------------------------------------


class _FakeProtectionAPI:
    def __init__(self, raw: dict) -> None:
        self._raw = raw

    def get_branch_protection(self, *, repo_full_name, branch, token, base_url):
        return self._raw


_DEFAULT_CONFIG = BranchProtectionConfig(
    required_status_checks=["ci/tests"],
    require_review=True,
    require_signed_commits=False,
    require_linear_history=False,
)


def test_branch_protection_passes_when_all_present() -> None:
    raw = {
        "required_pull_request_reviews": {"required_approving_review_count": 1},
        "required_status_checks": {"contexts": ["ci/tests"]},
    }
    verifier = BranchProtectionVerifier(api=_FakeProtectionAPI(raw), shadow_mode=False)
    result = verifier.verify(
        repo_full_name="org/repo",
        branch="main",
        token="tok",
        base_url="https://api.github.com",
        required_config=_DEFAULT_CONFIG,
    )
    assert result.passed is True
    assert result.missing == []


def test_branch_protection_fails_when_review_missing_in_shadow_mode() -> None:
    raw = {"required_status_checks": {"contexts": ["ci/tests"]}}
    verifier = BranchProtectionVerifier(api=_FakeProtectionAPI(raw), shadow_mode=True)
    result = verifier.verify(
        repo_full_name="org/repo",
        branch="main",
        token="tok",
        base_url="https://api.github.com",
        required_config=_DEFAULT_CONFIG,
    )
    assert result.passed is False
    assert "required_pull_request_reviews" in result.missing
    assert result.shadow_mode is True


def test_branch_protection_enforce_mode_blocks_on_missing() -> None:
    raw = {}
    verifier = BranchProtectionVerifier(api=_FakeProtectionAPI(raw), shadow_mode=False)
    result = verifier.verify(
        repo_full_name="org/repo",
        branch="main",
        token="tok",
        base_url="https://api.github.com",
        required_config=_DEFAULT_CONFIG,
    )
    assert result.passed is False
    assert result.shadow_mode is False


def test_null_api_returns_empty_dict_in_shadow_mode() -> None:
    verifier = BranchProtectionVerifier(api=_NullBranchProtectionAPI(), shadow_mode=True)
    result = verifier.verify(
        repo_full_name="org/repo",
        branch="main",
        token="",
        base_url="https://api.github.com",
        required_config=BranchProtectionConfig(
            required_status_checks=[],
            require_review=False,
            require_signed_commits=False,
            require_linear_history=False,
        ),
    )
    assert result.passed is True


def test_is_enforce_mode_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_BRANCH_PROTECTION_ENFORCE", "true")
    assert is_enforce_mode() is True
    monkeypatch.setenv("GITHUB_BRANCH_PROTECTION_ENFORCE", "false")
    assert is_enforce_mode() is False
    monkeypatch.delenv("GITHUB_BRANCH_PROTECTION_ENFORCE", raising=False)
    assert is_enforce_mode() is False


# ---------------------------------------------------------------------------
# CredentialPolicy PAT opt-in and rate limits
# ---------------------------------------------------------------------------


def test_credential_policy_github_app_allowed_with_full_rate_limit() -> None:
    policy = CredentialPolicy()
    record = CredentialRecord(
        tenant_id="t1",
        team_id="tm1",
        provider="github",
        credential_type="github_app",
        encrypted_payload="cipher",
        rotated_at=datetime.now(tz=UTC),
    )
    result = policy.validate(record)
    assert result.allowed is True
    assert result.rate_limit_per_hour == GITHUB_APP_RATE_LIMIT_PER_HOUR


def test_credential_policy_pat_without_opt_in_blocked() -> None:
    policy = CredentialPolicy()
    record = CredentialRecord(
        tenant_id="t1",
        team_id="tm1",
        provider="github",
        credential_type="pat",
        encrypted_payload="cipher",
        rotated_at=datetime.now(tz=UTC),
    )
    result = policy.validate(record)
    assert result.allowed is False
    assert result.reason == "pat_requires_explicit_opt_in"


def test_credential_policy_pat_with_valid_opt_in_gets_reduced_rate_limit() -> None:
    policy = CredentialPolicy()
    now = datetime.now(tz=UTC)
    record = CredentialRecord(
        tenant_id="t1",
        team_id="tm1",
        provider="github",
        credential_type="pat",
        encrypted_payload="cipher",
        rotated_at=now,
    )
    opt_in = PATOptInRecord(
        opt_in_id="oi-1",
        tenant_id="t1",
        team_id="tm1",
        approver_actor="super-admin-user",
        rationale="migration period",
        allowed_scopes=["repo"],
        expires_at=now + timedelta(days=30),
    )
    result = policy.validate(record, pat_opt_in=opt_in)
    assert result.allowed is True
    assert result.rate_limit_per_hour == GITHUB_PAT_RATE_LIMIT_PER_HOUR


def test_credential_policy_pat_opt_in_expired_blocks() -> None:
    policy = CredentialPolicy()
    now = datetime.now(tz=UTC)
    record = CredentialRecord(
        tenant_id="t1",
        team_id="tm1",
        provider="github",
        credential_type="pat",
        encrypted_payload="cipher",
        rotated_at=now - timedelta(days=5),
    )
    opt_in = PATOptInRecord(
        opt_in_id="oi-2",
        tenant_id="t1",
        team_id="tm1",
        approver_actor="super-admin-user",
        rationale="was valid",
        allowed_scopes=["repo"],
        expires_at=now - timedelta(days=1),
    )
    result = policy.validate(record, pat_opt_in=opt_in)
    assert result.allowed is False
    assert result.reason == "pat_opt_in_expired"


def test_credential_policy_rotation_overdue_blocks() -> None:
    policy = CredentialPolicy()
    old = datetime.now(tz=UTC) - timedelta(days=100)
    record = CredentialRecord(
        tenant_id="t1",
        team_id="tm1",
        provider="github",
        credential_type="github_app",
        encrypted_payload="cipher",
        rotated_at=old,
        rotation_window_days=90,
    )
    result = policy.validate(record)
    assert result.allowed is False
    assert result.reason == "rotation_overdue"


# ---------------------------------------------------------------------------
# EscalationReason.BRANCH_PROTECTION_MISSING in runtime models
# ---------------------------------------------------------------------------


def test_branch_protection_missing_escalation_reason_exists() -> None:
    assert EscalationReason.BRANCH_PROTECTION_MISSING == "branch_protection_missing"


def test_ticket_run_state_has_branch_protection_passed_field() -> None:
    req = PlanningRequest(summary="Add GitHub App integration")
    run = TicketRunState.new(req)
    assert run.branch_protection_passed is False
