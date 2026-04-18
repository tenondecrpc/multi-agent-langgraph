## 1. Finalize Trust Boundaries

- [x] 1.1 Confirm that tenant, team, repository, memory, credential, and visibility boundaries are all covered by the phase 3 specs.
- [x] 1.2 Confirm that GitHub App preference, envelope encryption, credential rotation, and break-glass expectations remain aligned with the repository constitution.
- [x] 1.3 Cross-check these capabilities against the runtime flow from phase 1 so security controls strengthen the flow instead of rewriting it.

## 2. Prepare Identity And Intake Contracts

- [x] 2.1 Define the future backend OIDC session and claim-mapping contract, including role, tenant, and team propagation.
- [x] 2.2 Define the future route protection and authorization contract for viewer, operator, admin, and super-admin behaviors.
- [x] 2.3 Define the future webhook verification, freshness, idempotency, and rate-limit middleware behavior for Jira and related intake surfaces.

## 3. Prepare Runtime Safety Enforcement

- [x] 3.1 Define the future prompt framing, output filtering, and sensitive-path escalation behavior for untrusted inputs.
- [x] 3.2 Define the future tool allowlist enforcement and policy-violation escalation contract for each runtime role.
- [x] 3.3 Define the future repository safety checks, secret scanning hooks, and signed-commit expectations that later coding and PR phases must honor.

## 4. Verification Readiness

- [x] 4.1 Define isolation validation that proves users and runs cannot cross tenant or team boundaries for data, credentials, or streams.
- [x] 4.2 Define webhook validation fixtures for invalid signatures, stale timestamps, duplicate events, and request floods.
- [x] 4.3 Define security validation fixtures for forbidden-path writes, prompt-injection attempts, secret findings, and missing branch protection.

## 5. Implement Contract-Level Security Slice

- [x] 5.1 Add backend security policy primitives for OIDC claim mapping, tenant- and team-scoped RBAC, and credential rotation enforcement.
- [x] 5.2 Add webhook, prompt-safety, tool-policy, and repository-policy modules that model the required security decisions without introducing live provider integrations yet.
- [x] 5.3 Add backend tests that cover invalid signatures, stale timestamps, duplicate deliveries, flood throttling, prompt-leak and secret findings, protected-path escalation, and missing branch protection.
- [x] 5.4 Verify the backend slice with `uv run --project backend ruff check backend/src backend/tests` and `uv run --project backend pytest` before archiving.
