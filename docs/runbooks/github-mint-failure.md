# Runbook: GitHub Installation Token Mint Failure

## Alert: `GitHubMintFailureRateHigh`

Fires when `github_mint_failure_total` exceeds 5 failures in 5 minutes for any installation.

## Impact

PR creation is blocked for affected tenants. Runs escalate to `ops://security-review` with `BRANCH_PROTECTION_MISSING` or stay at `PR_CREATOR` node with `INVALID_ROUTE_ATTEMPT`.

## Triage Steps

1. Check `github_mint_failure_total` by `reason` label:
   - `permission_drift_unacknowledged` - see [github-permission-drift runbook](./github-permission-drift.md)
   - `jwt_dependency_missing` - Python environment missing `PyJWT` or `cryptography`; check pod image
   - `empty_token_from_github` - GitHub API returned no token; check App installation status in GitHub settings
   - `vault_read_error` - Vault is unavailable or the secret path is wrong; check Vault health

2. Check Vault availability: `vault status`

3. Check the App installation on GitHub:
   - Navigate to `https://github.com/settings/installations/<github_installation_id>`
   - Verify the App is still installed and not suspended

4. Check recent `github_app_installed` / `github_app_uninstalled` audit log entries for the affected tenant.

## Recovery

- If Vault is down: restore Vault connectivity; minting resumes automatically on next attempt.
- If App was uninstalled: tenant must re-run the installation wizard (`POST /api/v1/admin/github/installations`).
- If permission drift: a `super_admin` must acknowledge drift via `POST /api/v1/admin/github/installations/{id}/acknowledge-drift`.

## Escalation

Page the on-call engineer if the failure rate persists beyond 15 minutes. Link this runbook in the PagerDuty alert.
