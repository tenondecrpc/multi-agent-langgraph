## 1. Finalize Platform Baseline

- [ ] 1.1 Confirm that the deployment topology covers connected and `air_gapped` profiles, the required workload inventory, and the planned repository structure.
- [ ] 1.2 Confirm that `local-minikube` is specified as a development profile only and is not treated as production equivalence.
- [ ] 1.3 Cross-check the platform baseline against the Tier 1 non-negotiables in `openspec/config.yaml`.

## 2. Prepare API And Worker Contracts

- [ ] 2.1 Define the future FastAPI route groups, OpenAPI publication rules, and backward-compatibility contract for `/api/v1`.
- [ ] 2.2 Define the future ARQ worker settings, queue metadata, fair dispatch behavior, and shutdown semantics required by the platform.
- [ ] 2.3 Define the future DLQ and retry capture interfaces so failed jobs remain inspectable and recoverable.

## 3. Prepare Sandbox And Namespace Contracts

- [ ] 3.1 Define the future Kubernetes Job template, gVisor runtime requirements, non-root image constraints, and tenant namespace isolation boundaries.
- [ ] 3.2 Define the future network policy, egress controls, cleanup jobs, and resource quota expectations for sandbox execution.
- [ ] 3.3 Define the future relationship between the primary worker pool and the shadow worker pool without implementing shadow-mode behavior in this phase.

## 4. Verification Readiness

- [ ] 4.1 Define dry-run validation for API surface stability, route versioning, and endpoint inventory coverage.
- [ ] 4.2 Define validation fixtures that prove worker draining preserves checkpoint boundaries and DLQ capture.
- [ ] 4.3 Define validation fixtures that prove sandbox workloads stay tenant-scoped, non-root, quota-bound, and removable by cleanup jobs.
