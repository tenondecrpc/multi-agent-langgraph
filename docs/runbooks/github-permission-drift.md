# Runbook: GitHub App Permission Drift

## Alert: `GitHubPermissionDriftDetected`

Fires when `github_permission_drift_total` is non-zero for any installation.
All mint calls for the affected installation are blocked until a `super_admin` acknowledges.

## Impact

PR creation is blocked for the affected tenant/team until drift is acknowledged and the expected permission hash is reconciled.

## Triage Steps

1. Identify the affected installation from the `installation_id` and `tenant_id` labels on the metric.

2. Retrieve the current permissions from GitHub:
   ```
   GET https://api.github.com/app/installations/<github_installation_id>
   Authorization: Bearer <app-jwt>
   ```

3. Compare current permissions against the `MINIMUM_REQUIRED_PERMISSIONS` in
   `backend/src/backend/integrations/github/permissions.py`.

4. Determine whether the drift is:
   - **Accidental** (someone edited App permissions in GitHub settings) - restore to least-privilege set
   - **Intentional** (new operation requires additional permission) - update `OPERATION_PERMISSIONS` and the expected hash

## Recovery

1. Restore the App to least-privilege permissions in GitHub settings, or update the permission baseline.
2. A `super_admin` acknowledges via:
   ```
   POST /api/v1/admin/github/installations/{installation_id}/acknowledge-drift
   X-Actor: <actor>
   X-Role: super_admin
   ```
3. The next drift scan will update `permissions_hash` and re-enable minting.

## Prevention

- Pin the GitHub App permission set in the `OPERATION_PERMISSIONS` map.
- Require pull requests for any changes to the App's OAuth scope in GitHub settings (done via CODEOWNERS-equivalent on GitHub App settings).

## Escalation

If the drift was caused by a security incident (permissions were expanded by an unauthorized party), escalate to the security team immediately.
