## Why

The previous change `fix-critical-security-and-infra-gaps` resolved encryption, fail-closed secrets, and auth middleware. This change completes the remaining critical gaps: Kubernetes resource governance (HPA, gVisor, security contexts, resource limits), LangGraph checkpoint integration for crash recovery, and executable chaos/fuzz/prompt regression tests. These are Tier 1 non-negotiables that must be resolved before production deployment.

## What Changes

- Add resource requests/limits to all backend, worker, and frontend pod templates
- Add HPA templates for backend, worker, and frontend
- Add gVisor RuntimeClass and sandbox Job template
- Add securityContext to all pod templates
- Change default image tags from `:latest` to `0.1.0`
- Add startupProbe and tune health probes
- Add analysis block to backend rollout
- Add PodDisruptionBudget templates
- Add topologySpreadConstraints
- Add ServiceAccount resources
- Parameterize Vault server URL
- Add missing env vars to worker rollout
- Wire PostgresSaver and PostgresStore into RuntimeWorkflow
- Use thread_id-based invocation for checkpoint resume
- Implement chaos test scenarios (worker kill, Redis partition, DB loss, budget race)
- Wire schemathesis fuzz tests against API endpoints
- Implement hypothesis-based config fuzz tests
- Create golden fixtures and implement prompt regression tests
- Run frontend tests

## Capabilities

### New Capabilities
- `k8s-resource-governance`: Resource limits, HPA, gVisor, security contexts in Helm charts
- `langgraph-checkpoints`: PostgreSQL-backed checkpoint integration for crash recovery
- `executable-chaos-fuzz-tests`: Real chaos injection and API fuzzing replacing TODO stubs

### Modified Capabilities
- None

## Impact

- **helm/templates/**: New HPA, gVisor, PDB, ServiceAccount templates; updated rollout/deployment templates
- **helm/values.yaml**: Default image tags changed, new resource limit values
- **backend/src/backend/runtime/workflow.py**: Checkpoint integration
- **backend/src/backend/persistence/factory.py**: Checkpoint saver and store building
- **backend/src/backend/app.py**: Pass checkpoint/store to workflow
- **backend/tests/chaos/**, **backend/tests/fuzz/**, **backend/tests/prompt_regression/**: Real test implementations
- **frontend/**: Test verification

**Risk**: High-risk change touching infrastructure and runtime. Helm changes require dry-run validation.
**Rollback**: Revert to previous commit. Checkpoint migration is backward-compatible.
**Non-goals**: Full config-driven graph compilation, PgBouncer integration, LLM invocation in workflow nodes.
