## Why

A security and infrastructure review identified 10 critical gaps that block any production deployment. These include fake encryption (base64 instead of AES), hardcoded default secrets, missing authentication on admin APIs, absent Kubernetes resource limits and HPA, no LangGraph checkpoint integration, and empty test scaffolds for chaos/fuzz/prompt regression. These are Tier 1 non-negotiable violations that must be resolved before the system can be deployed.

## What Changes

- Replace `EnvelopeCipher` with real AES-256-GCM encryption using Fernet from cryptography library
- Remove all hardcoded default secrets and fail closed on startup when encryption/webhook secrets are not configured
- Wire `AuthorizationPolicy` into all admin API routers as FastAPI dependencies
- Add resource requests/limits to all backend and worker pod templates in Helm charts
- Change default image tags from `:latest` to versioned tags matching `appVersion`
- Add HPA templates for backend, worker, and frontend with CPU/memory targets
- Add gVisor `RuntimeClass` and sandbox Job template with security contexts
- Wire `PostgresSaver` checkpoint integration into `RuntimeWorkflow` with thread-based state persistence
- Implement chaos test scenarios for worker kill, Redis partition, and database loss
- Wire schemathesis fuzz tests against actual API endpoints
- Implement prompt regression tests with golden output comparison
- Add Alembic migration for new encryption schema changes

## Capabilities

### New Capabilities
- `real-envelope-encryption`: AES-256-GCM envelope encryption with proper key rotation, replacing the base64+HMAC stub
- `fail-closed-secrets`: Startup validation that refuses to serve when encryption or webhook secrets are not configured
- `api-auth-middleware`: OIDC/RBAC authentication wired into all admin API routers
- `k8s-resource-governance`: Resource limits, HPA, gVisor sandbox, and security contexts in Helm charts
- `langgraph-checkpoints`: PostgreSQL-backed checkpoint integration for crash recovery and resume
- `executable-chaos-fuzz-tests`: Real chaos injection and API fuzzing replacing TODO stubs

### Modified Capabilities
- None (all are new capabilities addressing gaps, not changes to existing spec requirements)

## Impact

- **backend/src/backend/persistence/encryption.py**: Complete rewrite of EnvelopeCipher with real AES-256-GCM
- **backend/src/backend/persistence/webhook.py**: Remove hardcoded default secret, fail closed
- **backend/src/backend/persistence/factory.py**: Fail closed when secrets not configured
- **backend/src/backend/security/auth.py**: No changes needed, already has AuthorizationPolicy
- **backend/src/backend/compliance/admin.py**, **credentials/admin.py**, **webhook/admin.py**, **supply_chain/admission.py**: Wire auth dependencies
- **backend/src/backend/runtime/workflow.py**: Add checkpoint integration with PostgresSaver
- **backend/tests/chaos/**, **backend/tests/fuzz/**, **backend/tests/prompt_regression/**: Implement real tests
- **helm/templates/**: Add HPA, resource limits, gVisor RuntimeClass, security contexts
- **helm/values.yaml**: Change default image tags from `:latest` to versioned
- **backend/alembic/versions/**: New migration for encryption schema changes
- **backend/pyproject.toml**: Add `cryptography` dependency

**Risk**: High-risk change touching security, infrastructure, and runtime. Requires careful testing and rollback plan.
**Rollback**: Revert to previous commit. Encryption migration is backward-compatible (new column, old column preserved during transition).
**Non-goals**: This change does not implement full config-driven graph compilation, PgBouncer integration, or LLM invocation in workflow nodes. Those are separate changes.
