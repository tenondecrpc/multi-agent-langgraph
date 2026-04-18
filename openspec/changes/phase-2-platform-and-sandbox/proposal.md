## Why

The runtime contract is not enough by itself. The repository also needs an explicit OpenSpec phase for the self-hosted platform baseline, public API shape, worker operations, and sandbox execution plane that will host the ticket workflow.

## What Changes

- Define the self-hosted deployment topology, repository structure, connected and air-gapped profiles, and local development profile.
- Define the public API surface, versioning policy, and endpoint categories used by webhook intake, status, stream, auth callback, admin, and metering workflows.
- Define worker and queue operations for ARQ execution, weighted fairness, graceful shutdown, dead-letter handling, and scaling expectations.
- Define sandbox execution requirements for Kubernetes Jobs hardened with gVisor, per-tenant isolation, network restrictions, and cleanup behavior.
- Keep this phase SDD-only. No infrastructure manifests, backend services, or application code are introduced in this change.
- Classify this phase as Tier 1 because it covers mandatory self-hosted deployment, queueing, sandbox, and public API invariants.

## Capabilities

### New Capabilities
- `deployment-topology`: Self-hosted topology, repository structure, workload inventory, deployment profiles, and local development environment requirements.
- `api-surface-and-versioning`: Public API organization, endpoint categories, `/api/v1` versioning, OpenAPI stability, and deprecation expectations.
- `worker-queue-operations`: ARQ worker behavior, fair queueing, HPA assumptions, graceful shutdown, and dead-letter handling requirements.
- `sandbox-execution`: Hardened sandbox job requirements, gVisor, network policy, non-root execution, cleanup, and tenant quota expectations.

### Modified Capabilities
- None.

## Impact

- Future `backend/`, `frontend/`, `helm/`, and `docs/` scaffolding.
- FastAPI route design and OpenAPI contract planning.
- ARQ worker architecture, scaling, and recovery behavior.
- Kubernetes workload definitions, sandbox images, and tenant namespace strategy.
