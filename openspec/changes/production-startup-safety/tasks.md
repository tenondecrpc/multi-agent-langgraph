## 1. Artifact Alignment

- [ ] 1.1 Confirm scope tightens existing Tier 1 invariants and does not weaken any rule.
- [ ] 1.2 Reconcile profile names with `helm/values-*.yaml` and the air-gapped profile spec.

## 2. Boot Gate Specification

- [ ] 2.1 Specify the per-profile required configuration matrix.
- [ ] 2.2 Specify the structured error format for boot failures.
- [ ] 2.3 Specify the `recovery` profile semantics (webhook acceptance closed).

## 3. Readiness Probe Specification

- [ ] 3.1 Specify per-profile readiness behavior; remove the `not_configured` skip from non-`local` profiles.
- [ ] 3.2 Specify the runbook reference returned in the readiness payload.

## 4. Webhook-Path Gates

- [ ] 4.1 Specify gate order and rejection reason codes.
- [ ] 4.2 Specify the credential rotation block at the webhook layer.
- [ ] 4.3 Specify the break-glass grant honoring at the webhook layer.
- [ ] 4.4 Specify the DPA acknowledgement enforcement at the webhook layer.

## 5. IP Allowlist Migration

- [ ] 5.1 Specify the versioned-config entity and audit fields.
- [ ] 5.2 Specify the two-stage cutover and drift alert.
- [ ] 5.3 Specify the rollback path to environment values.

## 6. Drift Detection And Observability

- [ ] 6.1 Specify the metrics and alerts.
- [ ] 6.2 Specify the drift detection job cadence and audit row contract.

## 7. Verification (Specification Phase)

- [ ] 7.1 Confirm the spec preserves Tier 1 invariants and tightens them where promised.
- [ ] 7.2 Confirm both connected and air-gapped profiles are addressed.
- [ ] 7.3 Confirm the recovery profile cannot be used to accept new webhooks.

## 8. Implementation (Deferred)

- [ ] 8.1 Implementation of the boot gate, webhook gates, allowlist migration, and metrics is deferred to a follow-up apply.
