## 1. Dependencies and setup

- [x] 1.1 Add `cryptography` to `backend/pyproject.toml` dependencies
- [x] 1.2 Run `uv sync --project backend --dev` to install new dependency
- [x] 1.3 Verify `import cryptography` works in the backend environment

## 2. Real envelope encryption

- [x] 2.1 Rewrite `EnvelopeCipher` in `backend/src/backend/persistence/encryption.py` to use Fernet from `cryptography.fernet`
- [x] 2.2 Ensure `encrypt()` produces real ciphertext (not base64 of plaintext)
- [x] 2.3 Ensure `decrypt()` recovers original plaintext
- [x] 2.4 Ensure random nonce/IV so same plaintext produces different ciphertexts
- [x] 2.5 Support key rotation with active and previous keys
- [x] 2.6 Add backward-compatible decrypt for old base64 format (detect `enc::` prefix, decode and return)
- [x] 2.7 Update `EnvelopeCipherSettings` to remove `active_wrapping_key` default and require env vars
- [x] 2.8 Add `configured` property that checks all required env vars are set

## 3. Fail closed on missing secrets

- [x] 3.1 Remove `"development-wrapping-key"` default from `EnvelopeCipherSettings`
- [x] 3.2 Remove `"development-shared-secret"` default from `WebhookGuardSettings`
- [x] 3.3 Remove `"development-shared-secret"` from `InMemoryWebhookGuard` in `persistence/testing/security.py`
- [x] 3.4 Remove `"development-shared-secret"` from `build_persistence_adapters()` in `persistence/factory.py`
- [x] 3.5 Add startup validation in `create_app()` that raises `RuntimeError` if encryption is not configured
- [x] 3.6 Add startup validation in webhook guard that raises `RuntimeError` if secret is not configured

## 4. Auth middleware on admin routers

- [x] 4.1 Create `require_role()` FastAPI dependency factory in `security/auth.py`
- [x] 4.2 Wire auth into `compliance/admin.py` router builder with `Depends(require_role(AuthRole.ADMIN))`
- [x] 4.3 Wire auth into `credentials/admin.py` router builder
- [x] 4.4 Wire auth into `webhook/admin.py` router builder
- [x] 4.5 Wire auth into `supply_chain/admission.py` router builder
- [x] 4.6 Add `auth_policy` parameter to each router builder for testability

## 5. Kubernetes resource governance

- [ ] 5.1 Add `resources.requests` and `resources.limits` to backend rollout template
- [ ] 5.2 Add `resources.requests` and `resources.limits` to backend deployment template
- [ ] 5.3 Add `resources.requests` and `resources.limits` to worker rollout template
- [ ] 5.4 Add `securityContext` with `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false` to all pod templates
- [ ] 5.5 Create `helm/templates/hpa-backend.yaml` with CPU/memory targets
- [ ] 5.6 Create `helm/templates/hpa-worker.yaml` with CPU/memory targets
- [ ] 5.7 Create `helm/templates/hpa-frontend.yaml` with CPU/memory targets
- [ ] 5.8 Create `helm/templates/gvisor-runtimeclass.yaml` for gVisor RuntimeClass
- [ ] 5.9 Create `helm/templates/sandbox-job.yaml` for gVisor sandboxed code execution
- [ ] 5.10 Change default image tags in `helm/values.yaml` from `latest` to `0.1.0`
- [ ] 5.11 Add `startupProbe` to backend rollout and deployment templates
- [ ] 5.12 Add `initialDelaySeconds`, `periodSeconds`, `failureThreshold` to backend health probes
- [ ] 5.13 Add `analysis` block to backend rollout referencing the AnalysisTemplate
- [ ] 5.14 Add `PodDisruptionBudget` templates for backend, worker, and frontend
- [ ] 5.15 Add `topologySpreadConstraints` to all pod templates
- [ ] 5.16 Add `serviceAccountName` ServiceAccount resources to Helm templates
- [ ] 5.17 Parameterize Vault server URL in `secretstore.yaml` via Helm values
- [ ] 5.18 Add missing env vars to worker rollout (encryption, LangSmith, RAG, GitHub)

## 6. LangGraph checkpoint integration

- [ ] 6.1 Add `checkpoint_saver` and `graph_store` fields to `PersistenceAdapters` dataclass
- [ ] 6.2 Build `PostgresCheckpointSaverHandle` in `build_persistence_adapters()` for PostgreSQL mode
- [ ] 6.3 Build `PostgresStore` in `build_persistence_adapters()` for PostgreSQL mode
- [ ] 6.4 Add `checkpointer` and `store` parameters to `RuntimeWorkflow.__init__`
- [ ] 6.5 Pass `checkpointer` and `store` to `self.graph.compile()` in `RuntimeWorkflow`
- [ ] 6.6 Use `thread_id`-based invocation in `RuntimeWorkflow.execute()`
- [ ] 6.7 Update `app.py` to pass checkpoint saver and store to `RuntimeWorkflow`

## 7. Executable chaos tests

- [ ] 7.1 Implement `TestLLMGarbageOutput` with actual garbage detection assertion
- [ ] 7.2 Implement `TestAllProvidersDown` with circuit breaker state assertion
- [ ] 7.3 Implement `TestSandboxCrash` with crash injection
- [ ] 7.4 Implement `TestDatabaseLoss` with database connection drop and recovery
- [ ] 7.5 Implement `TestRedisPartition` with Redis connection blocking
- [ ] 7.6 Implement `TestBudgetRace` with concurrent reservation test

## 8. Executable fuzz tests

- [ ] 8.1 Wire schemathesis to OpenAPI spec in `test_api_fuzz.py`
- [ ] 8.2 Implement `test_webhook_rejects_malformed_payload` with schemathesis
- [ ] 8.3 Implement `test_admin_api_requires_authentication` with schemathesis
- [ ] 8.4 Implement `test_routing_selects_valid_provider` with hypothesis in `test_config_fuzz.py`
- [ ] 8.5 Implement `test_routing_respects_budget_cap` with hypothesis

## 9. Prompt regression tests

- [ ] 9.1 Create golden fixture for planner output in `prompt_regression/fixtures/`
- [ ] 9.2 Create golden fixture for reviewer output in `prompt_regression/fixtures/`
- [ ] 9.3 Implement `test_planner_regression_score_within_tolerance` with golden comparison
- [ ] 9.4 Implement `test_reviewer_regression_score_within_tolerance` with golden comparison

## 10. Tests and verification

- [x] 10.1 Write unit tests for new `EnvelopeCipher` encrypt/decrypt/rotation
- [x] 10.2 Write tests for fail-closed startup validation
- [x] 10.3 Write tests for auth middleware on admin endpoints
- [x] 10.4 Run `uv run --project backend ruff check backend/src backend/tests` and fix issues
- [x] 10.5 Run `uv run --project backend pytest` and verify all tests pass
- [ ] 10.6 Run `npm run --prefix frontend test -- --run` and verify frontend tests pass
