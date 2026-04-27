## ADDED Requirements

### Requirement: Deployment Profile Names Are Unambiguous

The backend SHALL distinguish Helm deployment profile values from backend runtime safety profiles. Helm values MAY use `profile: connected` or `profile: air_gapped` to select chart behavior, while `BACKEND_DEPLOYMENT_PROFILE` SHALL use one of `local`, `test`, `staging`, `production`, `air_gapped`, or `recovery` to select backend startup safety behavior. `helm/values-staging.yaml` and `helm/values-prod.yaml` SHALL map the connected chart profile to backend runtime profiles `staging` and `production` respectively. `helm/values-air-gapped.yaml` SHALL map to backend runtime profile `air_gapped`.

The backend SHALL reject unknown profile names at boot with reason `profile_unknown`. A connected chart profile SHALL NOT be treated as a backend runtime safety profile.

#### Scenario: Connected Helm production maps to production runtime profile
- **WHEN** the production Helm values render backend environment variables
- **THEN** `BACKEND_DEPLOYMENT_PROFILE` is `production`
- **AND** the backend applies the non-local boot gate and strict readiness contract

#### Scenario: Unknown runtime profile fails boot
- **WHEN** `BACKEND_DEPLOYMENT_PROFILE` is not one of the supported runtime profile values
- **THEN** startup fails with reason `profile_unknown`
- **AND** no in-memory fallback is selected

### Requirement: Non-Local Profiles Refuse To Start On In-Memory Adapters

When `BACKEND_DEPLOYMENT_PROFILE` is `staging`, `production`, `air_gapped`, or `recovery`, the backend SHALL refuse to start unless PostgreSQL, Redis, the configured secret backend, and the model catalog source are reachable. In-memory fallbacks SHALL be available only in `local` and `test` profiles.

The boot gate SHALL enforce the following profile matrix:

| Runtime profile | PostgreSQL URL | Redis URL | Secret backend | KEK reference | Signing key reference | Model catalog source | Webhook acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `local` | optional | optional | optional | optional | optional | optional bundled or memory | open after minimal signature gate |
| `test` | optional | optional | optional | optional | optional | optional fixtures | open for test harness only |
| `staging` | required and reachable | required and reachable | Vault or ESO required | required | required | PostgreSQL or reviewed bundled seed | open after full gates |
| `production` | required and reachable | required and reachable | Vault or ESO required | required | required | PostgreSQL authoritative source | open after full gates |
| `air_gapped` | required and reachable | required and reachable | internal Vault or ESO required | required | internal signing root required | bundled seed plus PostgreSQL reconciliation | open after full gates and vendor-egress denial |
| `recovery` | required and reachable | required and reachable | Vault or ESO required | required | required | PostgreSQL or reviewed bundled seed | closed with `recovery_profile_active` |

Boot failures SHALL be logged as structured JSON with `event_type=boot_failure`, `profile`, `reason`, `missing_requirements`, `unsafe_adapter`, `secret_backend`, `db_driver`, `redis_driver`, `runbook_url`, `timestamp`, and `pod_name` when available. If PostgreSQL is reachable, the backend SHALL also write an audit row with those fields plus `git_sha` and `helm_release`. If PostgreSQL is not reachable, the structured log is authoritative and the process exits before accepting traffic.

Required boot failure reason codes are `profile_unknown`, `postgresql_missing`, `postgresql_unreachable`, `redis_missing`, `redis_unreachable`, `secret_backend_missing`, `secret_backend_env_forbidden`, `kek_reference_missing`, `signing_key_reference_missing`, `model_catalog_missing`, `memory_adapter_forbidden`, and `air_gapped_vendor_dependency`.

#### Scenario: Production boot without database fails fast
- **WHEN** the pod starts in `production` without a database URL
- **THEN** startup fails with a structured boot-failure log
- **AND** the pod does not enter `Ready` state

#### Scenario: Local boot still allows in-memory adapters
- **WHEN** the pod starts in `local` without a database URL
- **THEN** startup succeeds using in-memory adapters
- **AND** readiness reports `local` profile

### Requirement: Readiness Probe Is Strict Outside Local And Test

In `staging`, `production`, `air_gapped`, and `recovery` profiles, the readiness probe SHALL report `not_ready` when the database, Redis, or migration state is `not_configured`. The current tolerance only applies to `local` and `test`.

For non-`local` and non-`test` profiles, `/readyz` SHALL return HTTP 503 when any required dependency is missing, unreachable, unhealthy, or reports migration state `not_configured`. The readiness payload SHALL include `status`, `profile`, `reasons`, `dependencies`, `migration_state`, `runbook_url`, and `recovery_allowed`. The `runbook_url` SHALL point to the production startup safety runbook or the closest existing persistence runbook until that runbook is implemented. `local` and `test` MAY return HTTP 200 with warnings when dependencies are not configured.

#### Scenario: Production readiness fails on missing migration state
- **WHEN** the pod runs in `production` and the migration state reports `not_configured`
- **THEN** `/readyz` returns `503` with reason `database_unhealthy` or `migration_drift`
- **AND** the response includes the runbook URL

#### Scenario: Local readiness reports warning
- **WHEN** the pod runs in `local` and PostgreSQL is not configured
- **THEN** `/readyz` may return `200`
- **AND** the payload includes profile `local` and warning `not_configured_tolerated`

### Requirement: Recovery Profile Closes Webhook Acceptance

The `recovery` profile SHALL boot with the same persistence and secret guarantees as `production`, but SHALL refuse to accept any webhook traffic. It exists only for disaster recovery inspection, repair, migration reconciliation, and administrative read or repair operations. It SHALL NOT enqueue new ticket runs, accept Jira or GitHub webhooks, mint new integration tokens for normal work, or run worker dispatch for new tenant traffic.

#### Scenario: Recovery boot rejects webhook
- **WHEN** the pod runs in `recovery` profile and a webhook arrives
- **THEN** the pod returns a structured rejection with reason `recovery_profile_active`
- **AND** the readiness probe stays `ok` for management endpoints

#### Scenario: Recovery cannot enqueue new work
- **WHEN** an operator attempts to enqueue a new ticket run while `recovery` is active
- **THEN** the request is rejected with reason `recovery_profile_active`
- **AND** the audit trail records that recovery mode blocked tenant traffic

### Requirement: Profile Drift Detection Records Runtime Safety State

A periodic drift detection job SHALL record the active runtime profile, rendered Helm profile, database driver, Redis driver, secret backend, migration state, model catalog source, and whether webhook acceptance is open. The job SHALL run at least every 5 minutes in `staging`, `production`, `air_gapped`, and `recovery`, and at least hourly in `local` or `test` when enabled.

The audit row SHALL include `event_type=deployment_profile_drift_check`, `profile`, `helm_profile`, `db_driver`, `redis_driver`, `secret_backend`, `migration_state`, `model_catalog_source`, `webhook_acceptance`, `safe`, `reasons`, `observed_at`, `pod_name`, `namespace`, `git_sha`, and `helm_release`.

#### Scenario: Non-local memory adapter alerts
- **WHEN** the drift job observes `profile=production` and `db_driver=memory`
- **THEN** `devsquad_deployment_profile_drift_total{reason="memory_adapter_forbidden"}` increments
- **AND** a critical alert references the startup safety runbook

### Requirement: Startup Safety Implementation Is Deferred Until Specification Completion

Implementation of the boot gate, strict readiness profile logic, recovery-profile webhook closure, drift detector, and metrics SHALL be deferred to a follow-up OpenSpec apply pass after this specification phase is complete. The follow-up implementation SHALL use this spec as the acceptance contract and include tests for every non-local profile and every boot failure reason code.

#### Scenario: Specification phase completes without boot gate code
- **WHEN** this OpenSpec change completes its artifact tasks
- **THEN** it may mark specification tasks complete without adding boot-gate code
- **AND** the next apply pass must implement the startup safety code before production readiness claims are made
