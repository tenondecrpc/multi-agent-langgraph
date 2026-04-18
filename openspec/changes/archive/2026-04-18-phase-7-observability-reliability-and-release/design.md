## Context

This phase converts the operational sections of `docs/PLAN.md` into product requirements instead of treating them as post-MVP hardening. The repository constitution already marks observability, SLOs, DR, progressive delivery, retention, and comprehensive testing as mandatory, so the OpenSpec roadmap needs a dedicated operations phase that can be implemented systematically later.

## Goals / Non-Goals

**Goals:**
- Define the observability surfaces, incident expectations, and public communication obligations for the product.
- Define concrete SLO and alerting policy that later release automation and operations dashboards can consume.
- Define HA and DR expectations, including restore drills and resilience controls.
- Define CI, migration, feature-flag, rollback, and environment parity requirements.
- Define the comprehensive quality-engineering baseline and retention or compliance operations.

**Non-Goals:**
- Frontend control-room design, graph editor behavior, or asset management.
- Auth, webhook trust, prompt filtering, or provider budget implementation.
- Kubernetes workload topology beyond what is necessary to express HA and release expectations.
- Vendor-specific implementation details for every observability or status component.

## Decisions

- Observability is defined as a contract across logs, metrics, traces, dashboards, probes, runbooks, and public status communication, not as a single monitoring tool choice.
- SLOs drive alerting and release policy through burn-rate logic instead of ad hoc raw-threshold alarms.
- HA and DR planning includes both topology and operational proof through backups, drills, and bounded recovery objectives.
- Release engineering couples CI safety gates, migration discipline, progressive delivery, rollback, and feature flags into one coherent control plane.
- Quality engineering explicitly includes chaos, fuzz, and prompt regression in addition to standard unit and integration coverage.
- Retention and compliance behavior are treated as product requirements because the platform stores checkpoints, memory, metering, and audit data over time.

## Risks / Trade-offs

- Operational scope is large, but leaving it implicit would directly conflict with the repository constitution.
- Some requirements reference external systems such as status pages, CI signers, or rollout controllers, which increases integration breadth later, but the product contract already assumes those responsibilities.
- Strict migration and release rules may slow delivery, but they are necessary to protect a self-hosted enterprise product from unsafe rollout behavior.

## Operations Coverage

This phase establishes the production baseline that all earlier phases must inherit.

| Operations concern | Contract outcome in this phase | Upstream dependency |
|---|---|---|
| Observability | Logs, metrics, traces, dashboards, and probes are product requirements, not optional tooling extras. | Covers runtime, platform, security, LLM, and control-plane surfaces from phases 1 through 6 |
| Incident response | Severity model, runbooks, and public communication become part of normal operations. | Relies on the escalation reasons and pause states defined earlier |
| SLO and alerting | SLI definitions, exclusions, burn-rate policies, and error-budget reporting are explicit. | Consumes API, queue, provider, and checkpoint signals from phases 2 through 5 |
| Release safety | CI, policy gates, progressive delivery, rollback, migration discipline, and feature flags are part of the release contract. | Applies to future backend, frontend, and Helm implementation |
| HA and DR | Recovery objectives, backups, restore drills, replica strategy, and resilience validation are mandatory. | Builds on phase 2 topology and phase 5 snapshot retention |
| Retention and compliance | Retention by data category, deletion workflows, and compliance evidence are formalized. | Builds on runtime state, memory, metering, audit, and DLQ storage contracts |

Alignment with `openspec/config.yaml`:

- Structured logs, metrics, traces, dashboards, alerting, SLOs, and incident runbooks remain Tier 1 mandatory.
- Progressive delivery, rollback, migration safety, backups, restore drills, and retention controls remain Tier 1 mandatory.
- Comprehensive testing remains broader than unit coverage and explicitly includes integration, E2E, chaos, fuzz, and prompt regression.

## Observability And SRE Interfaces

### Logging, Metrics, Tracing, Probes, And Dashboards

The future product should expose observability through explicit interfaces and common identity fields.

| Signal family | Required fields or behavior |
|---|---|
| Structured logs | `timestamp`, `level`, `service`, `component`, `tenant_id`, `team_id`, `run_id`, `trace_id`, `event_type`, `message` |
| Metrics | Stable names and labels for API, worker, queue, provider, config, and sandbox surfaces |
| Traces | End-to-end trace propagation across ingress, API, worker, sandbox, provider, and PR edges |
| Health probes | Liveness and readiness for API, workers, shadow workers, and supporting services |
| Dashboards | Packaged dashboards for intake, execution, failover, queue health, cost, and release state |

Observability rules:

- Tenant and team labels must support scoped investigation while respecting phase 3 visibility rules.
- Health probes must indicate whether a component can safely receive traffic or work, not just whether a process is running.
- Dashboard contracts must be shipped as part of product operations and versioned alongside product releases.

### Incident, Runbook, And Public Status Contract

The future SRE model should make incident handling explicit.

| Concern | Contract |
|---|---|
| Severity model | Incidents map to declared severity levels with response expectations |
| Runbooks | Pager-worthy signals must link to operator runbooks with remediation steps |
| Status communication | Customer-visible degradation can be published through a bounded component-aware status surface |
| Audit trail | Incident timeline, operator actions, and public updates remain auditable |

Rules:

- Missing runbook coverage for a pager-worthy alert is an operational gap.
- Public status communication should reflect component-level degradation rather than vague service-wide language when possible.

### SLI, Burn-Rate, And Error-Budget Interfaces

The future SLO engine should consume explicit measurement contracts.

```python
class SliDefinition(BaseModel):
    sli_id: str
    objective_percent: Decimal
    measurement_window: str
    numerator_query: str
    denominator_query: str
    exclusion_query: str | None = None
```

Interface expectations:

- Each SLO-backed surface declares its numerator, denominator, exclusion policy, and error-budget allowance.
- Burn-rate alert definitions must include the short and long windows used for paging and non-paging alerts.
- Error-budget reports should show healthy, low, and exhausted states tied to release policy decisions.

## Release, Resilience, And Retention Interfaces

### CI, Promotion, Rollout, Rollback, And Feature Flags

The future delivery pipeline should be modeled as explicit gates rather than one opaque release job.

| Stage | Required gates |
|---|---|
| Source validation | Linting, type or static analysis, complexity, duplication, unit tests, and policy scans |
| Integration validation | Real PostgreSQL, Redis, and sandbox-backed integration suite |
| Artifact production | Signed build artifacts, SBOM, provenance, and vulnerability policy checks |
| Staging promotion | Expand-first migrations, staging E2E validation, prompt regression, and rollout analysis readiness |
| Production rollout | Progressive delivery, health and burn-rate analysis, automated rollback triggers, feature-flag kill switches |

Release rules:

- Schema changes must follow expand-and-contract discipline with tested rollback or downgrade steps.
- High-risk subsystems such as provider routing or PR creation require kill-switch support through feature flags.
- Staging must remain the closest production mirror, not a reduced demo environment.

### HA And DR Contract

The future resilience model should make recovery behavior measurable.

| Area | Contract |
|---|---|
| Recovery objectives | Declared RPO and RTO for core control-plane data and service restoration |
| Backups | Scheduled backups for PostgreSQL and other required state with verification records |
| Restore drills | Periodic restore drills against representative state and bounded success criteria |
| Replica strategy | Intentional read, write, and connection-pool behavior for primaries and replicas |
| Resilience validation | Maintenance, failover, and partial-outage scenarios are tested intentionally |

Rules:

- Restore drill results become operational evidence and must be retained.
- Connection management and replica usage must stay explicit so read scaling does not accidentally break consistency-sensitive paths.

### Retention, Deletion, Cleanup, And Compliance Evidence

Retention should be category-driven rather than one global TTL.

| Data category | Contract |
|---|---|
| Checkpoints and runtime state | Retained long enough to support resume, audit, and bounded replay expectations |
| Long-term memory | Tenant-scoped retention and deletion rules distinct from checkpoints |
| Metering and billing data | Retained long enough to support invoicing, reconciliation, and audit |
| Audit and incident evidence | Retained according to security and compliance evidence obligations |
| DLQ and replay metadata | Retained long enough to support operational investigation and recovery |

Deletion rules:

- Tenant deletion and compliance actions must define the cascade order, protected exceptions, and evidence captured for the action.
- Cleanup jobs must respect pinned snapshots, active incidents, and declared retention exceptions before removing data.

## Verification Fixtures

| Task | Fixture definition | Expected proof |
|---|---|---|
| 4.1 SLO and alert validation | Replay traffic and failure patterns that include valid service failures plus excluded auth, stale webhook, and rate-limit events. | SLI calculations exclude the declared policy failures, and burn-rate rules fire at the expected severities and windows. |
| 4.2 DR validation | Execute backup creation, representative restore drills, and rollout rollback drills against declared RPO and RTO targets. | Operators can produce evidence that backups restore successfully and rollbacks complete within the bounded objectives. |
| 4.3 Quality suites | Run unit, integration, E2E, chaos, fuzz, and prompt-regression suites against the product slices that exist. | The release contract requires coverage across all declared layers, not only unit tests. |
| 4.4 CI gate validation | Attempt merges with failing lint, static analysis, complexity, duplication, or SOLID review signals. | Merge remains blocked until the required gates pass or an explicit tracked exception is granted where policy permits it. |
| 4.5 Coverage-floor and waiver validation | Simulate a pull request that drops unit or integration coverage below the declared floor. | The pipeline fails unless an auditable waiver is recorded, and waiver usage remains reportable later. |

These fixtures connect the full product baseline:

- Earlier phases define what the product must do.
- This phase defines how implementation and operations must prove that behavior remains safe, observable, and releasable.

## Implementation Slice

This phase now includes a contract-level backend operations slice under `backend/src/backend/operations/`, test coverage in `backend/tests/test_operations_contracts.py`, and operator-facing reference docs under `docs/`.

Implemented modules:

- `observability.py` models structured log events, dashboards, runbook registration, incident records, and public status updates.
- `slo.py` evaluates SLI observations with exclusions, burn-rate alert policy, and error-budget state reporting.
- `release.py` models staged release gates, rollout rollback triggers, migration discipline, feature flags, and environment intent.
- `resilience.py` evaluates DR objectives, restore drills, rollback drills, and HA replica-control expectations.
- `retention.py` models category-based retention, snapshot and incident protections, cleanup evidence, and tenant-deletion cascade order.
- `quality.py` models required suite coverage, coverage floors, waivers, and static gate enforcement.

Supporting docs:

- `docs/operations-runbook.md` captures severity levels, pager-worthy alerts, and drill evidence expectations.
- `docs/public-status-template.md` provides a bounded component-level status communication template.

Implementation boundaries:

- The slice is intentionally policy-oriented and in-memory. It does not replace the future monitoring stack, rollout controller, backup scheduler, or CI provider integration.
- The goal is to make the operational contract executable and testable inside the repository so later infrastructure work inherits a single production baseline.
