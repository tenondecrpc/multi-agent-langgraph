## 1. Artifact Alignment

- [x] 1.1 Confirm scope tightens existing Tier 1 invariants and does not weaken any rule.
- [x] 1.2 Reconcile profile names with `helm/values-*.yaml` and the air-gapped profile spec.

## 2. Boot Gate Specification

- [x] 2.1 Specify the per-profile required configuration matrix.
- [x] 2.2 Specify the structured error format for boot failures.
- [x] 2.3 Specify the `recovery` profile semantics (webhook acceptance closed).

## 3. Readiness Probe Specification

- [x] 3.1 Specify per-profile readiness behavior; remove the `not_configured` skip from non-`local` profiles.
- [x] 3.2 Specify the runbook reference returned in the readiness payload.

## 4. Webhook-Path Gates

- [x] 4.1 Specify gate order and rejection reason codes.
- [x] 4.2 Specify the credential rotation block at the webhook layer.
- [x] 4.3 Specify the break-glass grant honoring at the webhook layer.
- [x] 4.4 Specify the DPA acknowledgement enforcement at the webhook layer.

## 5. IP Allowlist Migration

- [x] 5.1 Specify the versioned-config entity and audit fields.
- [x] 5.2 Specify the two-stage cutover and drift alert.
- [x] 5.3 Specify the rollback path to environment values.

## 6. Drift Detection And Observability

- [x] 6.1 Specify the metrics and alerts.
- [x] 6.2 Specify the drift detection job cadence and audit row contract.

## 7. Verification (Specification Phase)

- [x] 7.1 Confirm the spec preserves Tier 1 invariants and tightens them where promised.
- [x] 7.2 Confirm both connected and air-gapped profiles are addressed.
- [x] 7.3 Confirm the recovery profile cannot be used to accept new webhooks.

## 8. Implementation (Deferred)

- [x] 8.1 Implementation of the boot gate, webhook gates, allowlist migration, and metrics is deferred to a follow-up apply.
