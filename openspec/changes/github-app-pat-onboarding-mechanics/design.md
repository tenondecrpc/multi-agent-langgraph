# Design: GitHub App and PAT Onboarding Mechanics

## Context

PLAN.md mandates GitHub App as the default and PAT as opt-in only. Phase 3 established credential isolation but did not deliver the install wizard, token minting, permission-drift detection, or branch-protection verification. The pr_creator node must refuse to create a PR when required protections are missing.

## Goals / Non-Goals

### Goals

- Tenant-scoped GitHub App installation and refresh lifecycle.
- On-demand installation-token minting with <=60 minute TTLs and no persistence.
- Explicit, audited PAT opt-in with stricter rate limits and visible admin-UI indicator.
- Mandatory branch-protection verification before PR creation.

### Non-Goals

- No vendor-hosted GitHub proxy. Each tenant talks to its configured GitHub (Cloud or Enterprise Server).
- No change to the diff-size guard, forbidden-path guard, review, or pre-PR sync gates beyond composing with this one.

## Decisions

### Decision: GitHub App installation record is the source of truth

A `github_app_installations` row captures `tenant_id`, `team_id`, `installation_id`, `account_login`, `permissions_hash`, `granted_at`, `revoked_at`. The minting service reads this row, fetches a JWT using the App private key (from Vault), exchanges it for a short-lived installation token, returns it to the caller, and never persists the token.

### Decision: PAT opt-in is a super_admin action

A `pat_opt_ins` row captures approver, rationale, tenant, team, allowed scopes, and expires_at. PAT credentials are stored as ciphertext. While PAT mode is active, a banner appears in the admin UI, the API-surface rate limit is halved, and the credential-rotation SLA applies to the PAT age.

### Decision: Permission drift is detected and surfaced

A scheduled job fetches the current permission set for each installation and compares it to the expected least-privilege hash. Drift raises a `github_permission_drift` event and blocks new mint calls until acknowledged by super_admin.

### Decision: Branch-protection verification runs before PR creation

Before the pr_creator node opens a PR, a guard fetches branch-protection settings, verifies required status checks, required reviews, required signed commits (when configured), and linear history (when configured). Missing protection routes to the `security_review` escalation sink; the PR is not created.

## Risks / Trade-offs

- Mint latency on cold path; mitigated by short token reuse within a request scope (never across runs).
- GitHub Enterprise Server feature variance; mitigated by capability probe per installation at boot.
- PAT fallback risk; mitigated by stricter rate limits, visible banner, and SLA-based expiry.

## Migration Plan

1. Add the installation record schema and minting service behind a feature flag.
2. Move existing credential usage through the onboarding record.
3. Add branch-protection verification in shadow mode; log but do not block for one release.
4. Flip shadow to enforce; wire `security_review` escalation.
5. Add permission-drift scan and PAT rate-limit enforcement.
