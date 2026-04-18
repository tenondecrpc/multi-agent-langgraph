## 1. Finalize Provider And Budget Scope

- [ ] 1.1 Confirm that provider routing, shared circuit-breaker behavior, budget caps, and all-providers-down handling match `docs/PLAN.md`.
- [ ] 1.2 Confirm that the phase captures the Tier 1 failover and budget guarantees without weakening air-gapped deployment support.
- [ ] 1.3 Cross-check the provider and budget specs against phase 1 runtime retries and escalation reasons.

## 2. Prepare LLM Control Interfaces

- [ ] 2.1 Define the future provider router interface, health-state storage contract, and role-to-model selection rules.
- [ ] 2.2 Define the future budget reservation and settlement interfaces, including worst-case estimation and orphaned reservation reconciliation.
- [ ] 2.3 Define the future model-catalog validation rules, token-cap derivation behavior, and air-gapped catalog overrides.

## 3. Prepare Metering And Billing Interfaces

- [ ] 3.1 Define the future usage-recording schema and rollup contracts for ticket, team, role, provider, and model attribution.
- [ ] 3.2 Define the future export API, rate-card versioning, reconciliation, and invoice-evidence interfaces.
- [ ] 3.3 Define the future observability hooks for failover, budget exhaustion, orphaned reservations, and billing drift.

## 4. Verification Readiness

- [ ] 4.1 Define failover validation for primary-provider outage, fallback-provider recovery, and all-providers-down pause-and-resume behavior.
- [ ] 4.2 Define concurrency validation that proves atomic reservations prevent budget overspend under parallel execution.
- [ ] 4.3 Define metering validation that proves exports, rollups, and reconciliation can be reproduced from usage records.
