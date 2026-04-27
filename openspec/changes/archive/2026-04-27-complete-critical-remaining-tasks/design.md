## Context

The previous change resolved encryption, fail-closed secrets, and auth middleware. This change completes the remaining critical gaps: K8s resource governance, LangGraph checkpoint integration, and executable tests.

## Goals / Non-Goals

**Goals:**
- Add resource limits, HPA, gVisor, security contexts, PDBs, ServiceAccounts to Helm charts
- Wire PostgresSaver and PostgresStore into RuntimeWorkflow
- Implement real chaos, fuzz, and prompt regression tests
- Run frontend tests

**Non-Goals:**
- Full config-driven graph compilation
- PgBouncer integration
- LLM invocation in workflow nodes

## Decisions

### Decision 1: HPA as separate templates
HPA and Argo Rollouts manage replicas differently. HPA handles metric-based scaling, Rollouts handle progressive delivery. Keeping them separate avoids conflicts.

### Decision 2: Checkpoint via PostgresSaver in workflow.compile()
LangGraph's native checkpoint support is the correct integration point. Using thread_id-based invocation enables crash recovery.

### Decision 3: Chaos tests use pytest fixtures with simulated failures
Real chaos injection requires Kubernetes. For unit tests, we simulate failures via mocking and connection manipulation.

## Risks / Trade-offs

- **[HPA and Rollouts conflict]**: HPA manages replicas while Rollouts also controls them. **Mitigation**: HPA targets the underlying Deployment, not the Rollout.
- **[Checkpoint latency]**: PostgreSQL checkpoints add latency per node. **Mitigation**: Connection pooling and monitoring.
- **[Chaos test flakiness]**: Simulated failures may be flaky. **Mitigation**: Mark with `@pytest.mark.chaos` and run in nightly job.
