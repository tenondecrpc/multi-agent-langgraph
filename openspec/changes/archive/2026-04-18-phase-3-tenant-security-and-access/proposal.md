## Why

The platform and runtime flow are only viable if tenant isolation, identity, webhook trust, prompt safety, and repository guardrails are specified as first-class capabilities. `docs/PLAN.md` defines these controls, but they need a dedicated OpenSpec phase so implementation cannot weaken them later under schedule pressure.

## What Changes

- Define tenant, team, repository, memory, and credential isolation requirements.
- Define OIDC authentication, four-tier RBAC, session handling, and backend-authoritative access checks.
- Define webhook and API protection requirements, including HMAC, freshness, idempotency, rate limiting, and rejection handling.
- Define prompt and tool safety requirements for untrusted ticket and repository content.
- Define repository, PR, secret, and supply-chain guardrails, including GitHub App preference, branch protection, signed commits, and secret scanning expectations.
- Add a contract-level backend security slice that implements claim mapping, RBAC policy checks, webhook guards, prompt safety checks, and repository safety decisions without introducing live identity-provider or Vault integrations yet.
- Classify this phase as Tier 1 because it covers tenant isolation, auth, webhook security, prompt defenses, and supply-chain safety.

## Capabilities

### New Capabilities
- `tenant-isolation-and-credentials`: Tenant and team boundaries, credential isolation, GitHub App preference, envelope encryption, and rotation expectations.
- `oidc-rbac-access`: OIDC login, four-tier RBAC, session management, and backend-authoritative authorization rules.
- `webhook-and-api-protection`: HMAC verification, timestamp freshness, idempotency, rate limiting, and rejected-request handling.
- `prompt-and-tool-safety`: Untrusted-input framing, tool allowlists, sensitive-path escalation, and response filtering expectations.
- `repository-and-supply-chain-guardrails`: Forbidden paths, branch protection, signed commits, secret scanning, SBOM, image signing, vulnerability scanning, and license policy expectations.

### Modified Capabilities
- None.

## Impact

- Future backend auth middleware, route dependencies, and Vault or ESO integration.
- Jira and GitHub webhook ingestion behavior.
- Sandbox and runtime tool policy enforcement.
- CI, image, and repository safety tooling planned in later phases.
- Backend verification now includes contract tests for the initial `backend.security` slice before this change can be archived.
