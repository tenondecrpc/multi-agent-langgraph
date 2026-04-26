# deployment-topology Specification

## Purpose
TBD - created by archiving change phase-2-platform-and-sandbox. Update Purpose after archive.
## Requirements
### Requirement: Self-Hosted Single-Customer Deployment Model

The product MUST deploy only inside customer-owned infrastructure and MUST not rely on a vendor-operated control plane or cross-customer data plane.

#### Scenario: Connected deployment remains customer-owned
- **WHEN** a customer deploys the connected profile
- **THEN** all application workloads, data stores, secrets, and provider accounts remain inside customer-owned infrastructure
- **AND** the product does not require a vendor-operated SaaS control plane to function

#### Scenario: Air-gapped deployment is first-class
- **WHEN** a customer deploys the `air_gapped` profile
- **THEN** the platform supports the same core product contract with self-hosted provider fallbacks and no external LLM egress
- **AND** the profile is planned from the start rather than added as a special-case exception later

### Requirement: Planned Repository And Workload Topology

The implementation roadmap MUST target a repository structure of `backend/`, `frontend/`, `helm/`, and `docs/`, backed by a Kubernetes topology that separates app, data, observability, and tenant sandbox workloads.

#### Scenario: Repository structure is fixed before implementation
- **WHEN** implementation work later begins
- **THEN** new code and deployment assets are organized under the planned top-level directories
- **AND** later phases extend this structure instead of inventing parallel roots

#### Scenario: Workload inventory covers required zones
- **WHEN** production topology is planned
- **THEN** the baseline inventory includes frontend, API, primary worker, shadow worker, PostgreSQL, Redis, observability workloads, and per-tenant sandbox jobs
- **AND** tenant sandboxes remain isolated from shared app workloads by namespace boundaries

### Requirement: Local Development Profile Is Explicitly Constrained

The `local-minikube` profile MUST exist for functional integration work, but it MUST be documented as non-equivalent to production HA, SLO, or security acceptance.

#### Scenario: Local profile keeps essential functional coverage
- **WHEN** a developer runs the local profile
- **THEN** ingress, queueing, sandbox jobs, and the core agent loop remain testable
- **AND** optional heavy observability or HA components may be reduced or disabled

#### Scenario: Local profile is not treated as production proof
- **WHEN** local profile validation succeeds
- **THEN** that result does not count as evidence for production HA, DR, or full hardening acceptance
- **AND** later phases still require production-grade validation for those concerns

### Requirement: Two First-Class Helm Profiles

The repository SHALL maintain two first-class Helm profiles: `connected` and `air_gapped`. CI SHALL validate both profiles on every change touching `helm/`, backend config, or the persistence backbone.

#### Scenario: PR touching Helm validates both profiles
- **WHEN** a PR changes Helm values or backend config
- **THEN** CI renders both profiles and runs dry-run plus the air-gapped smoke
- **AND** any rendering or smoke failure blocks the merge

