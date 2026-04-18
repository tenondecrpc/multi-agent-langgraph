## 1. Finalize Platform Baseline

- [x] 1.1 Confirm that the deployment topology covers connected and `air_gapped` profiles, the required workload inventory, and the planned repository structure.
- [x] 1.2 Confirm that `local-minikube` is specified as a development profile only and is not treated as production equivalence.
- [x] 1.3 Cross-check the platform baseline against the Tier 1 non-negotiables in `openspec/config.yaml`.

## 2. Prepare API And Worker Contracts

- [x] 2.1 Define the future FastAPI route groups, OpenAPI publication rules, and backward-compatibility contract for `/api/v1`.
- [x] 2.2 Define the future ARQ worker settings, queue metadata, fair dispatch behavior, and shutdown semantics required by the platform.
- [x] 2.3 Define the future DLQ and retry capture interfaces so failed jobs remain inspectable and recoverable.

## 3. Prepare Sandbox And Namespace Contracts

- [x] 3.1 Define the future Kubernetes Job template, gVisor runtime requirements, non-root image constraints, and tenant namespace isolation boundaries.
- [x] 3.2 Define the future network policy, egress controls, cleanup jobs, and resource quota expectations for sandbox execution.
- [x] 3.3 Define the future relationship between the primary worker pool and the shadow worker pool without implementing shadow-mode behavior in this phase.

## 4. Verification Readiness

- [x] 4.1 Define dry-run validation for API surface stability, route versioning, and endpoint inventory coverage.
- [x] 4.2 Define validation fixtures that prove worker draining preserves checkpoint boundaries and DLQ capture.
- [x] 4.3 Define validation fixtures that prove sandbox workloads stay tenant-scoped, non-root, quota-bound, and removable by cleanup jobs.

## 5. Implement Phase 2 Platform Contracts

- [x] 5.1 Extend the backend FastAPI app with explicit `/api/v1` route groups for webhook intake, runs, streams, auth callback, admin profile, and metering export surfaces.
- [x] 5.2 Implement executable weighted-fair dispatch, worker drain, and dead-letter capture helpers that express the planned ARQ worker contract in code.
- [x] 5.3 Implement sandbox and worker-pool contract models for tenant-scoped namespaces, gVisor runtime requirements, non-root execution, cleanup labels, and primary versus shadow pool separation.
- [x] 5.4 Add automated tests for route inventory coverage, worker fairness and drain semantics, and sandbox template isolation defaults.
- [x] 5.5 Run `uv`-based lint and backend tests after the platform changes and keep phase 2 unarchived unless the checks pass.
