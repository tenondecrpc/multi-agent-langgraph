## 1. Artifact Alignment

- [ ] 1.1 Confirm scope strengthens the existing supply-chain change rather than reopening it.
- [ ] 1.2 Reconcile pinned versions with `renovate.json` grouping.

## 2. Pinned Versions

- [ ] 2.1 Specify `scripts/supply_chain_versions.json` schema.
- [ ] 2.2 Specify renewal cadence per tool and the force-renew path on CVE.
- [ ] 2.3 Specify the automated PR opener for pin renewals.

## 3. Dry-Run Check

- [ ] 3.1 Specify the tiny dry-run image and its location.
- [ ] 3.2 Specify the validator assertions per step.
- [ ] 3.3 Specify the deliberate-failure variant to prove each assertion can fail.

## 4. Fail-Closed Contract

- [ ] 4.1 Specify the four required outputs.
- [ ] 4.2 Specify the dual super-admin override path and audit row.
- [ ] 4.3 Specify the alert when the override is used.

## 5. Permissions Composite Action

- [ ] 5.1 Specify the composite action contract.
- [ ] 5.2 Specify the migration path from per-job permissions blocks to the composite.

## 6. Release Evidence

- [ ] 6.1 Specify the `release-evidence.json` schema.
- [ ] 6.2 Specify the runbook reference and audit retention.

## 7. Observability

- [ ] 7.1 Enumerate metrics and alerts.

## 8. Verification (Specification Phase)

- [ ] 8.1 Confirm the spec preserves Tier 1 invariants.
- [ ] 8.2 Confirm fail-closed cannot be silently disabled.

## 9. Implementation (Deferred)

- [ ] 9.1 Implementation of the version pin file, dry-run image, validator, composite action, and renewal opener is deferred to a follow-up apply.
