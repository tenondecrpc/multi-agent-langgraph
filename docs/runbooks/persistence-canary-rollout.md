# Persistence Canary Rollout

- Use the Helm rollout values in `helm/values.yaml`.
- Start with 5 percent traffic, then 25 percent, 50 percent, and 100 percent if SLOs remain healthy.
- Watch `devsquad_persistence_operation_seconds`, `devsquad_dlq_depth`, `devsquad_provider_circuit_breaker_state`, and burn-rate alerts during each pause.
- Roll back immediately if migration drift, DLQ growth, or kill-switch activation appears.

## Automated Rollback Triggers

- `health_regressed`
- `burn_rate_threshold_exceeded`
- `kill_switch_engaged`

## Kill Switches

- `ops-webhook-guard-cutover`
- `ops-run-repository-cutover`
- `ops-control-plane-store-cutover`
- `ops-worker-controller-cutover`
- `ops-budget-ledger-cutover`
- `ops-metering-ledger-cutover`
- `ops-model-catalog-cutover`
- `ops-provider-health-cutover`
