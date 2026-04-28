# Runbook: GitHub Permission Drift Detected

## Alert: GitHubPermissionDriftDetected

### Summary
A tenant's GitHub repository permissions no longer match the expected RBAC snapshot.

### Impact
- Repo-write agents may lack required permissions.
- Branch-protection enforcement may silently fail.

### Diagnosis

1. Compare the current GitHub App installation permissions against the stored snapshot.
2. Check the `github_permission_drift` audit log entries.

### Mitigation

1. Re-install or re-approve the GitHub App for the affected organization.
2. Re-run the permission snapshot job via the admin API.
3. If the drift was intentional, update the stored snapshot to match.

### Verification

- Run the `permission_reconciliation` check.
- Confirm no new `github_permission_drift` events are emitted.

### Escalation
If the drift cannot be resolved via re-installation, escalate to `ops://github-auth`.
