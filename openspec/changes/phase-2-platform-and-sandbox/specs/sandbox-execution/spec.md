## Non-Goals

- Defining branch protection or repo safety policy.
- Defining provider failover or LLM budget behavior.
- Defining UI controls for sandbox status.

## ADDED Requirements

### Requirement: Hardened Per-Tenant Sandbox Jobs

Repo-writing and test execution MUST run inside hardened Kubernetes Jobs isolated by tenant-aware boundaries.

#### Scenario: Sandbox execution is isolated by tenant
- **WHEN** a ticket requires code execution or test execution
- **THEN** the runtime launches a sandbox job in a tenant-scoped namespace or equivalent isolated boundary
- **AND** the sandbox does not share writable execution state with other tenants

#### Scenario: gVisor and non-root execution are mandatory
- **WHEN** sandbox workloads are planned
- **THEN** they run with gVisor or an equivalent hardened runtime plus non-root execution
- **AND** rootful or unrestricted sandbox execution is not accepted as a v1 baseline

### Requirement: Network And Resource Controls Are Enforced

Sandbox jobs MUST have explicit network egress controls, resource quotas, and cleanup semantics.

#### Scenario: Sandbox egress is constrained
- **WHEN** sandbox workloads are allowed network access
- **THEN** their egress is limited to the minimum approved surfaces needed for the ticket flow
- **AND** unrestricted outbound internet access is not assumed

#### Scenario: Sandbox resources remain bounded
- **WHEN** multiple jobs execute in parallel
- **THEN** each tenant's sandbox workloads remain subject to planned CPU, memory, and quota boundaries
- **AND** the sandbox plane cannot grow without bound due to a single tenant or failed cleanup

### Requirement: Sandbox Lifecycle Is Maintainable

The platform MUST define cleanup behavior for orphaned jobs, pods, and volumes created by sandbox execution.

#### Scenario: Cleanup removes abandoned sandbox resources
- **WHEN** sandbox jobs fail, are interrupted, or outlive their expected execution window
- **THEN** scheduled cleanup removes orphaned resources
- **AND** cleanup does not delete active sandbox resources that are still owned by a live run

### Requirement: Sandbox Images Are Hardened

Sandbox container images MUST be planned as minimal, signed, and hardened images rather than ad hoc developer shells.

#### Scenario: Sandbox images remain least-privilege
- **WHEN** the sandbox image contract is implemented later
- **THEN** the image uses a minimal package set, disables privileged execution patterns, and supports readiness checks appropriate for job execution
- **AND** later supply-chain policies can verify the image without changing this baseline contract
