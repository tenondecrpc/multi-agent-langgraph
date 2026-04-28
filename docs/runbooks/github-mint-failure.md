# Runbook: GitHub Mint Failure Rate High

## Alert: GitHubMintFailureRateHigh

### Summary
The GitHub App installation token minting failure rate is above the configured threshold.

### Impact
- PR creation and branch-protection checks may fail for all tenants using GitHub App authentication.
- The `pr_creator` node will escalate to `ops://github-auth`.

### Diagnosis

1. Check the backend logs for `github_mint_failure` telemetry events.
2. Verify the GitHub App private key PEM is valid and not expired.
3. Check the GitHub App rate limit status.

### Mitigation

1. If the private key is expired, rotate it via Vault or the admin credential-rotation endpoint.
2. If rate limits are hit, verify the `GITHUB_APP_RATE_LIMIT_PER_HOUR` budget is not exhausted.
3. As a break-glass measure, tenants can temporarily switch to PAT authentication (more restricted).

### Verification

- Run the `github_app_health` probe via `/api/v1/admin/platform/health/github`.
- Confirm minting telemetry shows `success` within 5 minutes.

### Escalation
If the issue persists after key rotation, escalate to `ops://github-auth`.
