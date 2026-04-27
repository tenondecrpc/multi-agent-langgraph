## 1. K8s resource governance - Helm templates

- [x] 1.1 Add `resources.requests` and `resources.limits` to backend rollout template
- [x] 1.2 Add `resources.requests` and `resources.limits` to backend deployment template
- [x] 1.3 Add `resources.requests` and `resources.limits` to worker rollout template
- [x] 1.4 Add `securityContext` to all pod templates
- [x] 1.5 Create `helm/templates/hpa-backend.yaml`
- [x] 1.6 Create `helm/templates/hpa-worker.yaml`
- [x] 1.7 Create `helm/templates/hpa-frontend.yaml`
- [x] 1.8 Create `helm/templates/gvisor-runtimeclass.yaml`
- [x] 1.9 Create `helm/templates/sandbox-job.yaml`
- [x] 1.10 Change default image tags from `latest` to `0.1.0`
- [x] 1.11 Add `startupProbe` to backend rollout and deployment
- [x] 1.12 Tune health probes with `initialDelaySeconds`, `periodSeconds`, `failureThreshold`
- [x] 1.13 Add `analysis` block to backend rollout
- [x] 1.14 Add PDB templates for backend, worker, frontend
- [x] 1.15 Add `topologySpreadConstraints` to all pod templates
- [x] 1.16 Add ServiceAccount resources
- [x] 1.17 Parameterize Vault server URL in `secretstore.yaml`
- [x] 1.18 Add missing env vars to worker rollout

## 2. LangGraph checkpoint integration

- [x] 2.1 Add `graph_store` field to `PersistenceAdapters` dataclass
- [x] 2.2 Build `PostgresStore` in `build_persistence_adapters()`
- [x] 2.3 Add `checkpointer` and `store` parameters to `RuntimeWorkflow.__init__`
- [x] 2.4 Pass `checkpointer` and `store` to `self.graph.compile()`
- [x] 2.5 Use `thread_id`-based invocation in `RuntimeWorkflow.execute()`
- [x] 2.6 Update `app.py` to pass checkpoint saver and store to `RuntimeWorkflow`

## 3. Executable chaos tests

- [x] 3.1 Implement `TestLLMGarbageOutput` with actual assertion
- [x] 3.2 Implement `TestAllProvidersDown` with circuit breaker assertion
- [x] 3.3 Implement `TestSandboxCrash` with crash injection
- [x] 3.4 Implement `TestDatabaseLoss` with connection drop and recovery
- [x] 3.5 Implement `TestRedisPartition` with Redis connection blocking
- [x] 3.6 Implement `TestBudgetRace` with concurrent reservation test

## 4. Executable fuzz tests

- [x] 4.1 Wire schemathesis to OpenAPI spec in `test_api_fuzz.py`
- [x] 4.2 Implement `test_webhook_rejects_malformed_payload`
- [x] 4.3 Implement `test_admin_api_requires_authentication`
- [x] 4.4 Implement `test_routing_selects_valid_provider` with hypothesis
- [x] 4.5 Implement `test_routing_respects_budget_cap` with hypothesis

## 5. Prompt regression tests

- [x] 5.1 Create golden fixture for planner output
- [x] 5.2 Create golden fixture for reviewer output
- [x] 5.3 Implement `test_planner_regression_score_within_tolerance`
- [x] 5.4 Implement `test_reviewer_regression_score_within_tolerance`

## 6. Verification

- [x] 6.1 Run `uv run --project backend ruff check backend/src backend/tests` and fix
- [x] 6.2 Run `uv run --project backend pytest` and verify all pass
- [x] 6.3 Run `npm run --prefix frontend test -- --run` and verify pass
