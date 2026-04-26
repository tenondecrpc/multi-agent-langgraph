## 1. Artifact Alignment

- [x] 1.1 Reconcile this proposal with Phase 3 credential-isolation and Phase 2 API-surface archived specs; confirm no Tier 1 rule is weakened.

## 2. Onboarding Record And Minting Service

- [x] 2.1 Add `github_app_installations`, `github_integration_credentials`, `pat_opt_ins`, and `branch_protection_verifications` tables via Alembic expand migration with reversibility test.
- [x] 2.2 Implement the installation wizard endpoints and the admin-UI flow with AA contrast and keyboard reachability.
- [x] 2.3 Implement the installation-token minting service using Vault-held App private key; enforce 60-minute TTL and no persistence.

## 3. PAT Opt-In

- [x] 3.1 Implement super_admin opt-in endpoint with actor, rationale, allowed scopes, expires_at, and audit event.
- [x] 3.2 Surface the persistent "PAT mode" banner in the admin UI.
- [x] 3.3 Apply stricter per-tenant GitHub rate limits in PAT mode and integrate PAT age into the credential-rotation SLA.

## 4. Least-Privilege And Drift Detection

- [x] 4.1 Encode expected permission set per operation; block any call missing a required permission.
- [x] 4.2 Scheduled drift-reconciliation job that emits `github_permission_drift` events and freezes mint calls on drift.

## 5. Branch-Protection Verification

- [x] 5.1 Implement the branch-protection pre-PR guard; route to `security_review` escalation sink when required protection is missing.
- [x] 5.2 Shadow-mode enforcement first release: log but do not block.
- [x] 5.3 Flip to enforce; verify mandatory chain integrity via an E2E smoke test.

## 6. Observability And Alerts

- [x] 6.1 Metrics: mint-latency p95, mint-failure rate, permission-drift count, branch-protection-failure count.
- [x] 6.2 Alerts and runbooks for mint failures and drift; link from the status-page work.

## 7. Verification

- [x] 7.1 `uv run --project backend ruff check` and `uv run --project backend pytest` green; integration tests use VCR fixtures for GitHub API.
- [x] 7.2 Frontend accessibility non-negotiable subset verified on the wizard and PAT banner.
- [x] 7.3 Helm values for App ID and private-key reference; connected and `air_gapped` profiles documented.

## 8. Archive

- [ ] 8.1 Archive via `openspec-archive-change` only after tests, review, and drift-scan live in production.
