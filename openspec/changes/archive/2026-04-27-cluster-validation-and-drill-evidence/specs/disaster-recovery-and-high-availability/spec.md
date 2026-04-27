## ADDED Requirements

### Requirement: Drill Program Reinforces Existing Operational Runbooks

The validation evidence program SHALL bind existing runbooks and operational specs to executable drills rather than creating a parallel source of truth. Drill definitions SHALL reference the relevant runbook under `docs/runbooks/`, the relevant OpenSpec capability, and the Tier 1 controls exercised by the drill. The program SHALL NOT introduce a new evidence database, a new alerting backend, customer-production drills, vendor-hosted control planes, or cross-customer data planes.

The drill catalog SHALL be documented in `docs/drills/catalog.md`, and the Tier 1 coverage matrix SHALL be documented in `docs/drills/coverage-matrix.md`. These files SHALL be generated in a follow-up implementation pass from the contract in this specification.

#### Scenario: Drill references existing runbook
- **WHEN** an operator opens a drill definition
- **THEN** the definition names the existing runbook or spec that owns the operational procedure
- **AND** the drill does not duplicate or contradict that runbook

#### Scenario: No new evidence datastore is introduced
- **WHEN** drill evidence is recorded
- **THEN** structured files are stored under `docs/drills/evidence/<drill>/<run-id>/`
- **AND** audit references use the existing PostgreSQL audit path where an application audit row is required

### Requirement: Drill Catalog Covers Tier 1 Controls

The drill catalog SHALL enumerate each drill's cadence, target profile, destructiveness, dual-control requirement, deliberate-failure variant, and Tier 1 control coverage. Required drills are:

| Drill | Cadence | Profile target | Destructive | Dual-control | Deliberate-failure variant |
| --- | --- | --- | --- | --- | --- |
| `ephemeral-k3s-admission-integration` | per commit | ephemeral connected and `air_gapped` fixtures | no | no | deploy unsigned or unattested image and assert admission rejection |
| `air-gapped-bundle-verification` | weekly | `air_gapped` lab | no | no | remove mirrored trust root or bundle manifest entry and assert verification failure |
| `all-providers-down-failover` | weekly | staging connected and `air_gapped` fallback | no | no | disable every configured provider and assert fail-closed escalation |
| `mid-traffic-webhook-secret-rotation` | monthly | staging connected | no | no | present expired or previous secret after grace window and assert webhook rejection |
| `progressive-delivery-rollback` | monthly | staging connected and `air_gapped` flag fallback | no | no | inject failed canary metric and assert automated rollback |
| `paging-escalation` | monthly | staging | no | no | suppress first responder acknowledgement and assert escalation policy advances |
| `weighted-fair-queue-load` | monthly | staging | no | no | overload one tenant queue and assert other tenants retain scheduled throughput |
| `sandbox-egress-and-gvisor` | monthly | ephemeral | no | no | attempt forbidden egress or privileged execution and assert denial |
| `api-diff-and-version-gate` | monthly | CI fixture | no | no | introduce breaking OpenAPI diff and assert gate failure |
| `dlq-and-graceful-shutdown` | monthly | staging | no | no | force worker shutdown mid-run and assert checkpoint-boundary stop plus DLQ routing |
| `kek-rotation` | quarterly | staging synthesized tenant | yes | yes | attempt single-approver or stale-approval rotation and assert denial |
| `dr-backup-and-restore` | quarterly | staging synthesized tenant | yes | yes | corrupt or omit a backup artifact and assert restore validation fails |
| `gdpr-tenant-erasure` | quarterly | staging synthesized tenant | yes | yes | omit one cascade-governed table and assert post-drill detection |

Each Tier 1 control in the constitution SHALL be covered by at least one drill or by a documented static gate plus a scheduled drill. The coverage matrix SHALL include at minimum:

| Tier 1 control group | Required drill or gate coverage |
| --- | --- |
| Parallel ticket processing, weighted-fair queueing, dead letter queue, graceful shutdown | `weighted-fair-queue-load`, `dlq-and-graceful-shutdown` |
| Kubernetes-native deployment, Helm, HPA, health probes, gVisor sandboxes | `ephemeral-k3s-admission-integration`, `sandbox-egress-and-gvisor` |
| Tenant and team isolation across credentials, data, memory, budgets, and queues | `weighted-fair-queue-load`, `kek-rotation`, `gdpr-tenant-erasure` |
| OIDC authentication and four-tier RBAC | `paging-escalation`, admission flip approval checks, static RBAC gate |
| LLM budget governance and provider failover | `all-providers-down-failover`, `weighted-fair-queue-load` |
| Sandbox hardening, egress controls, non-root execution | `sandbox-egress-and-gvisor` |
| Envelope encryption, Vault or external KMS, credential rotation SLA, dual-control break-glass | `kek-rotation`, `mid-traffic-webhook-secret-rotation` |
| GitHub App default, PAT opt-in restrictions, webhook security, rate limiting | `mid-traffic-webhook-secret-rotation`, static GitHub integration gate |
| Merge conflict detection, diff size guard, forbidden path guard, signed commits, branch protection | static pre-PR policy gates plus `api-diff-and-version-gate` |
| Prompt injection defenses and secret scanning | supply-chain CI gate plus `ephemeral-k3s-admission-integration` evidence linkage |
| Supply chain security, SBOM, signing, provenance, admission enforcement | `ephemeral-k3s-admission-integration`, `air-gapped-bundle-verification` |
| PostgreSQL-backed config, audit, metering, schema migration discipline | `dr-backup-and-restore`, `api-diff-and-version-gate` |
| Observability, SLOs, burn-rate alerting, public status, incident runbooks | `paging-escalation`, `progressive-delivery-rollback` |
| Disaster recovery, backups, restore drills, RPO and RTO | `dr-backup-and-restore` |
| Progressive delivery, automated rollback, feature-flag kill switches | `progressive-delivery-rollback` |
| Public API versioning and diff gates | `api-diff-and-version-gate` |
| Data retention, deletion, and DPA acknowledgement | `gdpr-tenant-erasure` |
| Connected and `air_gapped` deployment profiles | `air-gapped-bundle-verification`, `ephemeral-k3s-admission-integration`, `progressive-delivery-rollback` |
| Comprehensive testing including chaos, fuzz, prompt regression | drill catalog plus separate quality program evidence |

#### Scenario: Tier 1 coverage matrix has no uncovered row
- **WHEN** the coverage matrix is generated
- **THEN** every Tier 1 control group has at least one drill or static gate reference
- **AND** any uncovered control fails the catalog validation command

#### Scenario: Destructive drill requires synthesized tenant
- **WHEN** a destructive drill is scheduled
- **THEN** it targets only a synthesized tenant or ephemeral fixture environment
- **AND** it records both dual-control approver identities before execution starts

### Requirement: Drill Evidence Is Structured And Time-Bounded

Every drill run SHALL produce a structured evidence bundle under `docs/drills/evidence/<drill>/<run-id>/` with metadata, inputs, observations, metrics, optional screenshots, and a status file. A signed timestamp SHALL be included.

The evidence directory contract SHALL be:

```
docs/drills/evidence/<drill>/<run-id>/
  metadata.json
  inputs.json
  observations.md
  metrics.csv
  status.json
  manifest.sig
  screenshots/
```

`metadata.json` SHALL include `schema_version`, `run_id`, `drill`, `cadence`, `profile`, `environment`, `started_at`, `finished_at`, `actor`, `approvers`, `git_sha`, `tool_versions`, `run_hash`, `signed_timestamp`, `signature_ref`, and `source_run_url`. `inputs.json` SHALL include sanitized fixture identifiers, target namespaces, synthetic tenant identifiers, policy revisions, and explicit confirmation that no real customer tenant was targeted. `status.json` SHALL include `result`, `failure_reason`, `deliberate_failure_result`, `incident_id`, `evidence_valid_until`, and `rollback_required`.

The signed timestamp mechanism SHALL hash a canonical manifest of every evidence file except `manifest.sig`, then sign that hash with the existing release or operator signing identity. In connected deployments the signature MAY use keyless signing with the GitHub Actions OIDC identity. In `air_gapped` deployments the signature SHALL use the configured internal signing root or pre-provisioned offline operator key. Evidence validation SHALL fail if any file hash changes after signing.

#### Scenario: Quarterly DR drill produces evidence
- **WHEN** the DR backup-and-restore drill completes
- **THEN** the evidence directory contains the documented files
- **AND** the metadata file includes a signed timestamp and a hash of the run

#### Scenario: Tampered evidence is rejected
- **WHEN** an evidence file is changed after `manifest.sig` is produced
- **THEN** the evidence validator reports `signature_invalid`
- **AND** the drill run no longer counts as fresh evidence

### Requirement: Stale Evidence Is Treated As Missing

Evidence older than its validity window SHALL be treated as missing. Operators SHALL NOT consult expired evidence to advance gated decisions.

Validity windows SHALL be:

- Per-commit drills: valid only for the commit or until a newer commit on the protected branch.
- Weekly drills: 14 days.
- Monthly drills: 60 days.
- Quarterly drills: 120 days.

Freshness SHALL be computed from the signed `finished_at` timestamp, not from file modification time.

#### Scenario: Expired DR evidence blocks audit claim
- **WHEN** a DR drill evidence bundle is older than 120 days
- **THEN** the freshness check reports `expired`
- **AND** the admission flip gate refuses to consult that evidence

### Requirement: Destructive Drills Use Synthesized Tenants

Destructive drills (KEK rotation, tenant erasure, DR restore) SHALL run on synthesized tenants in staging or an ephemeral lab. They SHALL NOT target real customer tenants.

#### Scenario: Tenant erasure drill targets fixture tenant
- **WHEN** the GDPR erasure drill runs
- **THEN** the drill operates on a fixture tenant identifier reserved for drills
- **AND** the dual-control approval records both approver identities

### Requirement: Drill Failures Trigger SEV2 Internal Incidents

Any failed drill, expired required evidence, failed deliberate-failure detection, or admission flip attempted with stale evidence SHALL open or update a SEV2 internal incident. The incident SHALL route through the existing incident and PagerDuty path, link the evidence directory, name the failed Tier 1 controls, and remain open until a passing rerun produces fresh evidence or an explicit risk acceptance is recorded through the existing break-glass approval process.

Metrics SHALL include:

- `devsquad_drill_runs_total{drill,result,profile}`.
- `devsquad_drill_evidence_age_days{drill,profile}`.
- `devsquad_drill_evidence_expired_total{drill,profile}`.
- `devsquad_drill_deliberate_failure_detections_total{drill,result}`.
- `devsquad_drill_incidents_total{drill,severity}`.
- `devsquad_admission_flip_gate_denials_total{reason}`.

Alerts SHALL cover drill failure, evidence expiry, missing deliberate-failure evidence, destructive drill without dual-control, and admission flip attempted with stale evidence. Dashboards SHALL include a drill calendar, freshness map, Tier 1 coverage heatmap, and incident status panel.

#### Scenario: Failed drill opens SEV2
- **WHEN** any required drill finishes with `failed` or `incomplete`
- **THEN** a SEV2 internal incident is opened or updated
- **AND** the incident links the evidence directory, runbook, failed control, and rerun instructions

#### Scenario: Dashboard shows stale evidence
- **WHEN** evidence is past its validity window
- **THEN** the drill freshness dashboard marks the drill stale
- **AND** the stale state is not represented by color alone

### Requirement: Drill Implementation Is Deferred Until Specification Completion

The implementation of drill scripts, ephemeral K3s harnesses, evidence validators, evidence catalog files, admission flip tooling, and dashboards SHALL be deferred to a follow-up OpenSpec apply pass after this specification phase is complete. The follow-up implementation SHALL use this specification as the acceptance contract and SHALL include validation for catalog coverage, evidence signatures, freshness windows, deliberate-failure variants, and SEV2 incident creation.

#### Scenario: Specification phase completes without drill scripts
- **WHEN** this OpenSpec change completes its artifact tasks
- **THEN** it may mark specification tasks complete without adding executable drill scripts or evidence tooling
- **AND** the next apply pass must implement those files before the change is eligible for production readiness claims

## Non-Goals

- Running drills against real customer production tenants.
- Creating a new evidence database or alerting backend.
- Replacing existing runbooks under `docs/runbooks/`.
- Weakening any Tier 1 control when evidence is missing or expired.
