## 1. Finalize Trust Boundaries

- [ ] 1.1 Confirm that tenant, team, repository, memory, credential, and visibility boundaries are all covered by the phase 3 specs.
- [ ] 1.2 Confirm that GitHub App preference, envelope encryption, credential rotation, and break-glass expectations remain aligned with the repository constitution.
- [ ] 1.3 Cross-check these capabilities against the runtime flow from phase 1 so security controls strengthen the flow instead of rewriting it.

## 2. Prepare Identity And Intake Contracts

- [ ] 2.1 Define the future backend OIDC session and claim-mapping contract, including role, tenant, and team propagation.
- [ ] 2.2 Define the future route protection and authorization contract for viewer, operator, admin, and super-admin behaviors.
- [ ] 2.3 Define the future webhook verification, freshness, idempotency, and rate-limit middleware behavior for Jira and related intake surfaces.

## 3. Prepare Runtime Safety Enforcement

- [ ] 3.1 Define the future prompt framing, output filtering, and sensitive-path escalation behavior for untrusted inputs.
- [ ] 3.2 Define the future tool allowlist enforcement and policy-violation escalation contract for each runtime role.
- [ ] 3.3 Define the future repository safety checks, secret scanning hooks, and signed-commit expectations that later coding and PR phases must honor.

## 4. Verification Readiness

- [ ] 4.1 Define isolation validation that proves users and runs cannot cross tenant or team boundaries for data, credentials, or streams.
- [ ] 4.2 Define webhook validation fixtures for invalid signatures, stale timestamps, duplicate events, and request floods.
- [ ] 4.3 Define security validation fixtures for forbidden-path writes, prompt-injection attempts, secret findings, and missing branch protection.
