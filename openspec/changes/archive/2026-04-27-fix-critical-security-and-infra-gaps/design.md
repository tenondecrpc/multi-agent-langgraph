## Context

The LangGraph Dev Squad has 10 critical gaps identified in a security and infrastructure review. The system is in early implementation with functional backend and frontend slices but missing production-grade security, infrastructure, and test infrastructure. The gaps span encryption (fake base64 instead of AES), hardcoded secrets, missing auth on admin APIs, absent Kubernetes resource governance, no LangGraph checkpoint integration, and empty test scaffolds.

## Goals / Non-Goals

**Goals:**
- Replace fake encryption with real AES-256-GCM envelope encryption
- Fail closed on startup when secrets are not configured
- Wire OIDC/RBAC auth into all admin API routers
- Add resource limits, HPA, gVisor, and security contexts to Helm charts
- Integrate PostgreSQL checkpoints into RuntimeWorkflow for crash recovery
- Implement real chaos, fuzz, and prompt regression tests

**Non-Goals:**
- Full config-driven graph compilation (separate change)
- PgBouncer integration (separate change)
- LLM invocation in workflow nodes (separate change)
- Frontend accessibility fixes (separate change)
- Complete E2E ticket pipeline test (separate change)

## Decisions

### Decision 1: Use Fernet from cryptography for envelope encryption
**Rationale**: Fernet provides AES-128-CBC with HMAC-SHA256 in a single primitive. It is well-tested, has a simple API, and handles nonce/IV generation internally. Alternative was raw AES-256-GCM via `cryptography.hazmat`, which is more complex and error-prone. Fernet is sufficient for envelope encryption where the wrapping key is itself protected by Vault/KMS.
**Alternatives considered**: Raw AES-256-GCM (more complex, higher risk of implementation errors), libsodium/PyNaCl (additional dependency, less standard in Python ecosystem).

### Decision 2: Fail closed with RuntimeError on missing secrets
**Rationale**: The system must refuse to start rather than fall back to known defaults. This is a security-first approach that prevents accidental deployment with weak secrets. The `EnvelopeCipher.__init__` and `PostgresRedisWebhookGuard.__init__` will validate configuration and raise `RuntimeError` if not properly configured.
**Alternatives considered**: Logging warnings and continuing (unsafe), using environment-specific defaults (still risky).

### Decision 3: Wire auth via FastAPI Depends() on each router
**Rationale**: Using FastAPI's dependency injection allows per-router auth configuration and easy testing with mock policies. A global middleware would be harder to test and less flexible for per-endpoint role requirements.
**Alternatives considered**: Global middleware (less flexible, harder to test), decorator-based auth (more boilerplate).

### Decision 4: HPA as separate templates, not inline in rollouts
**Rationale**: HPA and Argo Rollouts have different scaling mechanisms. HPA handles horizontal scaling based on metrics, while Rollouts handle progressive delivery. Keeping them separate allows independent configuration and avoids conflicts.
**Alternatives considered**: Inline HPA in rollout spec (not supported by Argo Rollouts).

### Decision 5: Checkpoint integration via PostgresSaver in workflow.compile()
**Rationale**: LangGraph's native checkpoint support via `PostgresSaver` is the correct integration point. The `RuntimeWorkflow` already accepts a `repository` parameter; adding `checkpointer` and `store` parameters follows the same pattern.
**Alternatives considered**: Custom checkpoint implementation (reinvents LangGraph functionality), in-memory checkpoints (not durable).

### Decision 6: Chaos tests use pytest fixtures with actual failure injection
**Rationale**: Real chaos tests need to inject actual failures (kill processes, block network, drop connections). pytest fixtures with `subprocess` and `socket` manipulation provide this without external tooling.
**Alternatives considered**: Chaos Mesh (requires Kubernetes cluster, too heavy for unit tests), Gremlin (vendor dependency).

## Risks / Trade-offs

- **[Encryption migration risk]**: Existing "encrypted" data in the database is base64-encoded and will not be decryptable with the new cipher. **Mitigation**: Add a migration that re-encrypts existing data. During transition, support both old and new formats via a version prefix in ciphertext.
- **[Auth wiring risk]**: Adding auth to all admin routers may break existing API consumers that do not send OIDC tokens. **Mitigation**: Add a `BACKEND_AUTH_REQUIRED` env var that defaults to `true` but can be set to `false` for migration period.
- **[HPA and Rollouts conflict]**: HPA and Argo Rollouts both manage replica counts. **Mitigation**: Configure HPA to manage the rollout's underlying deployment, not the rollout itself. Use Argo Rollouts' built-in HPA integration.
- **[Checkpoint performance]**: PostgreSQL checkpoints add latency to each graph node execution. **Mitigation**: Use connection pooling and tune `pool_size`. Monitor checkpoint write latency via Prometheus metrics.
- **[Chaos test flakiness]**: Chaos tests that inject real failures may be flaky in CI. **Mitigation**: Mark chaos tests with `@pytest.mark.chaos` and run them in a separate nightly job with retries.

## Migration Plan

1. Add `cryptography` to `pyproject.toml` and run `uv sync`
2. Rewrite `EnvelopeCipher` with Fernet, keeping backward-compatible decrypt for old base64 format
3. Add Alembic migration for any schema changes (new encryption metadata columns)
4. Remove hardcoded defaults from `webhook.py`, `factory.py`, `encryption.py`
5. Wire `AuthorizationPolicy` into all admin routers
6. Update Helm templates with resource limits, HPA, gVisor, security contexts
7. Wire `PostgresSaver` and `PostgresStore` into `RuntimeWorkflow`
8. Implement chaos, fuzz, and prompt regression tests
9. Run full test suite and verify all tests pass
10. Run `uv run --project backend ruff check` and fix any lint issues

**Rollback**: Revert to previous commit. Encryption migration is backward-compatible during transition (old format still decryptable).

## Open Questions

- Should the encryption migration include a data re-encryption job, or should old data be re-encrypted on next read/write? **Decision**: Re-encrypt on next write (lazy migration) to avoid a long-running migration job.
- Should HPA be enabled by default in values.yaml or opt-in? **Decision**: Enabled by default for backend and worker, opt-in for frontend.
