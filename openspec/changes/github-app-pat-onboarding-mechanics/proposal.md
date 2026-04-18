## Why

The constitution makes GitHub App the default integration path and PAT usage an explicit opt-in with more restricted scope; PLAN.md specifies installation-token minting, least-privilege permission set, branch-protection verification, and a PAT-opt-in flag surfaced in the admin UI. None of this is covered by the archived phases or by the active persistence change. Without it, no tenant can reach GitHub in production and the PR creation path cannot verify branch protection or signed commits, which is a Tier 1 non-negotiable.

## What Changes

- Add a tenant-scoped GitHub integration onboarding flow: GitHub App installation wizard, org scope capture, installation-ID storage, on-demand installation-token minting with short TTLs, and rotation of JWT signing keys.
- Require a least-privilege GitHub App permission set (contents, pull_requests, checks, metadata, actions read as needed) documented per operation; forbid broader scopes.
- Add explicit PAT opt-in path: requires super_admin approval, records actor and rationale, surfaces a persistent "PAT mode" flag in the admin UI, applies stricter per-tenant GitHub rate limits, and records PAT age against the credential-rotation SLA.
- Enforce branch-protection verification before any PR creation: required checks, required reviews, required signed commits, require linear history if configured; missing protection escalates to `security_review` and blocks PR creation.
- Add GitHub App permission-drift detection and alerting; mint-call failure circuit breaker; audit events for install, uninstall, permission change, PAT opt-in, and PAT rotation.
- **BREAKING** for any caller that hard-codes PAT usage: must route through the integration onboarding record and permission check.

## Capabilities

### New Capabilities

- `github-app-onboarding-and-permissions`: contract for GitHub App install lifecycle, installation-token minting, least-privilege permission set, PAT opt-in discipline, permission-drift detection, and branch-protection verification before PR creation.

### Modified Capabilities

- `tenant-isolation-and-credentials`: integration credentials for GitHub now flow through the onboarding record, never through environment variables; PAT usage is flagged, restricted, and auditable.
- `repository-and-supply-chain-guardrails`: branch-protection verification is a mandatory pre-PR gate; missing protection blocks PR creation and escalates.

## Impact

- Code: new `backend/src/backend/integrations/github/` module, extends `security/credentials.py` and the pr_creator node; admin UI surfaces installation wizard and PAT-mode banner.
- Schema: `github_app_installations`, `github_integration_credentials` (ciphertext columns), `pat_opt_ins`, `branch_protection_verifications`.
- Secrets: GitHub App private key stored via Vault; installation tokens never persisted.
- Deployment: Helm values for GitHub App ID and private-key reference; air-gapped profile accepts GitHub Enterprise Server endpoints configured per tenant.
- Observability: install and permission-drift metrics, mint-failure alerts, branch-protection-failure escalation metric.
- Tests: unit, integration (VCR against GitHub API), and chaos tests for mint failure and permission drift.
- Constitution alignment: Tier 1 preserved; GitHub App is default, PAT is restricted opt-in, branch protection is mandatory.
