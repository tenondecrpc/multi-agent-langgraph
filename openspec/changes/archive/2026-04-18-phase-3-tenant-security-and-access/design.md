## Context

This phase turns the trust model from `docs/PLAN.md` into explicit capability contracts. The product is self-hosted and multi-tenant inside a single customer deployment, which means auth, credential handling, webhook trust, and repository safety cannot be left as implementation details scattered across backend and infrastructure work.

## Goals / Non-Goals

**Goals:**
- Define tenant and team isolation for credentials, data visibility, memory, budgets, and repository scope.
- Define OIDC and four-tier RBAC requirements with backend-authoritative enforcement.
- Define webhook authenticity, freshness, idempotency, and rate-limit protections for external intake.
- Define prompt-safety and tool-boundary rules for untrusted ticket and repository content.
- Define repository and supply-chain guardrails that later coding and release phases must obey.

**Non-Goals:**
- Kubernetes sandbox hardening details, queue internals, or API topology planning.
- LLM provider routing, budgets, metering, or billing export.
- Graph config activation, shadow-mode comparison, or frontend administration design.
- Observability thresholds, release rollout steps, or disaster recovery drills.

## Decisions

- Multi-tenancy remains strictly within one customer-owned deployment, with tenant and team boundaries enforced at every data, credential, and visibility surface.
- Credentials are treated as service-layer material only. They are never passed into the LLM context and are stored envelope-encrypted with tenant-scoped key material managed through Vault or KMS patterns.
- GitHub App installation tokens are the default credential path. PAT usage remains opt-in and more restricted.
- OIDC claims drive frontend guards and backend authorization, but backend enforcement is the source of truth.
- Webhook security is layered across authenticity, freshness, source restrictions, idempotency, and throttling so one missed control does not collapse the entire trust boundary.
- Untrusted ticket, repository, and diff content is treated as data, not instructions, and tool privileges remain defined by role policy rather than user-provided content.
- Repository safety, secret scanning, and supply-chain controls are baseline product requirements, not optional enterprise add-ons.

## Risks / Trade-offs

- This phase centralizes several security domains in one slice, but separating them would increase the chance of inconsistent trust boundaries.
- Self-hosted deployment increases variation in customer environments, so these specs must stay principle-driven while still remaining testable.
- Tight repository and supply-chain guardrails may slow future implementation work, but that cost is preferable to allowing security-sensitive shortcuts to become the default path.

## Trust Boundary Coverage

This phase strengthens the runtime contract from phase 1 rather than replacing it.

| Security concern | Contract outcome in this phase | Phase 1 relationship |
|---|---|---|
| Tenant and team isolation | Repository access, credentials, memory, budget scope, and visibility stay bound to tenant and authorized team scopes. | Reuses the same `tenant_id`, `team_id`, `run_id`, and `thread_id` boundaries already defined for runtime execution. |
| Credential handling | Secrets stay in service-layer storage and delivery paths only, protected by envelope encryption and rotation policy. | Preserves the rule that planner, coder, tester, reviewer, and PR creator do not receive raw credentials in model context. |
| GitHub App default | Installation tokens remain the standard integration identity, with PAT fallback explicitly constrained and more auditable. | Leaves the phase 1 success path intact while changing only how credentials are acquired. |
| OIDC and RBAC | User identity and role scope are resolved before protected routes or break-glass controls are allowed. | Controls who may trigger or inspect runtime behavior without changing the graph's success-path ordering. |
| Webhook trust | HMAC, freshness, idempotency, and flood protection apply before enqueueing runtime work. | Ensures only trusted intake can create a phase 1 run. |
| Prompt and tool safety | Untrusted content stays framed as data, tool use stays role-bound, and sensitive paths escalate. | Adds protective checks around runtime nodes instead of redefining planner, coder, or reviewer semantics. |
| Repo and supply-chain safety | Forbidden-path writes, secret findings, unsigned commits, and missing branch protection block automatic PR flow. | Extends the guarded path before PR creation without opening new shortcuts. |

Alignment with the repository constitution:

- Tier 1 invariants preserved: tenant isolation, OIDC and RBAC, webhook protection, prompt injection defenses, secret scanning, signed provenance, and branch protection checks remain mandatory.
- Break-glass expectations remain explicit: overdue rotation, `security_review`, or policy-violation paths may interrupt the run, but normal success still cannot require manual approval.
- Security controls attach to the phase 1 runtime flow as preconditions, wrappers, or guarded branches. They do not reorder planner-owned artifacts, mandatory tests, or review.

## Identity And Intake Contracts

### Future OIDC Session And Claim Mapping Contract

The backend should normalize identity provider claims into a stable internal auth context.

```python
class AuthContext(BaseModel):
    subject_id: str
    tenant_id: str
    team_ids: list[str]
    role: Literal["viewer", "operator", "admin", "super-admin"]
    session_id: str
    expires_at: datetime
    break_glass_grants: list[str] = []


class ClaimMapper(Protocol):
    async def map_claims(self, raw_claims: Mapping[str, Any]) -> AuthContext: ...
```

Mapping expectations:

- OIDC claim mapping must produce a single authoritative `tenant_id` plus the user's authorized team scopes.
- Role mapping must collapse identity-provider-specific group or attribute layouts into the repository's four-tier RBAC model.
- Session evaluation must re-check expiry and role scope so stale privilege changes do not survive indefinitely.
- Break-glass grants must be explicit, time-bounded, and auditable rather than inferred from broad admin roles.

### Route Protection And Authorization Matrix

Backend authorization stays authoritative for every protected surface.

| Role | Allowed actions | Explicitly restricted actions |
|---|---|---|
| `viewer` | Read run summaries, logs, metrics, and non-sensitive UI views within tenant and team scope | No retries, config changes, interrupts, credential access, or DLQ replay |
| `operator` | Viewer permissions plus retries, interrupts on registered exception paths, and DLQ inspection within scope | No tenant-wide config edits, credential management, or cross-team administration |
| `admin` | Operator permissions plus agent and graph config changes, policy tuning, and tenant-scoped administration | No cross-tenant operational visibility unless explicitly granted |
| `super-admin` | Cross-tenant operational administration and break-glass surfaces with audit requirements | No implicit bypass of audit, signing, or repo-safety policies |

Authorization contract:

- Route dependencies must evaluate both role and scope, not role alone.
- Tenant and team filters apply to API responses, SSE streams, and operator actions consistently.
- Frontend route guards may hide unavailable features, but the API must remain the final enforcement point.

### Webhook Verification Middleware Contract

Webhook intake should be processed through a stable middleware chain:

1. Source allowlist and request-shape sanity checks
2. HMAC or equivalent authenticity verification
3. Timestamp freshness check
4. Idempotency lookup and deduplicated success handling
5. Rate-limit and flood protection
6. Audit logging and enqueue decision

```python
class WebhookGuardResult(BaseModel):
    accepted: bool
    deduplicated: bool = False
    rejection_reason: str | None = None
    idempotency_key: str | None = None


class WebhookGuard(Protocol):
    async def verify(self, request: "WebhookRequest") -> WebhookGuardResult: ...
```

Middleware rules:

- Invalid signature and stale timestamp failures must reject before queueing and before idempotency treats the request as a valid replay.
- Duplicate accepted events should return a deduplicated success response rather than enqueueing a second run.
- Rate-limit rejections must be auditable and visible as security or intake events, not normal ticket failures.

## Runtime Safety Enforcement

### Prompt Framing, Output Filtering, And Sensitive Paths

The runtime should treat untrusted input as data through explicit prompt envelopes.

```python
class PromptEnvelope(BaseModel):
    trusted_instructions: str
    untrusted_context_blocks: list[str]
    forbidden_actions: list[str]
```

Prompt-safety rules:

- Ticket text, repository files, diffs, search results, and semi-trusted retrieved content must be clearly delimited from trusted system instructions.
- Output filtering must screen for credential-like content, hidden instruction leakage, prompt exfiltration attempts, and other unsafe payloads before downstream use.
- Sensitive path detection must occur both on planned changes and produced diffs. Touching protected surfaces routes the run to `security_review` instead of the ordinary success path.

### Tool Allowlist Enforcement By Runtime Role

Role policy should be explicit and machine-validatable.

| Runtime role | Allowed tool families | Escalation trigger |
|---|---|---|
| Planner | Jira, repository read, checkpoint and memory read, approved first-party lookup, bounded research | Attempt to write repo, bypass context order, or use forbidden external actions |
| Coder | Repository write within allowed paths, local test commands, approved build tooling | Attempt to access credentials, protected paths, or disallowed network research |
| Tester | Test execution, static analysis, artifact read, sandbox controls needed for validation | Attempt to modify policy, secrets, or unrelated repositories |
| Reviewer | Repository read, diff analysis, policy checks, bounded first-party lookup | Attempt to mutate repo or bypass enforced quality and safety gates |
| PR creator | Git metadata, PR creation, Jira update, final policy verification | Attempt to create PR without satisfied guards or to modify protected repo content |

Tool-policy rules:

- Allowlists must be versioned configuration, not prompt text only.
- Violations escalate with a specific policy reason and tool family so operators can distinguish accidental misuse from malicious prompts.
- Future phase 5 config controls may tune tools within a role's envelope, but they may not grant capabilities outside the role boundary.

### Repository Safety, Secret Scanning, And Signed Commits

The backend should enforce repo safety through a dedicated policy service.

```python
class RepositoryPolicyDecision(BaseModel):
    allowed: bool
    escalation_reason: str | None = None
    blocked_paths: list[str] = []


class RepositoryPolicy(Protocol):
    async def evaluate_diff(self, diff: "PlannedOrObservedDiff") -> RepositoryPolicyDecision: ...
```

Policy expectations:

- Forbidden path classes include protected branches, CI config, infra, Dockerfiles, secrets, and CODEOWNERS-class files unless the constitution is explicitly amended.
- Secret scanning hooks run on generated diffs, commit messages, PR text, and other outbound artifacts before they leave the system.
- Signed commits and provenance metadata are mandatory inputs to later PR creation and release workflows.
- Missing branch protection or missing signing capability is a policy failure, not a warning.

## Verification Fixtures

| Task | Fixture definition | Expected proof |
|---|---|---|
| 4.1 Isolation validation | Use multiple tenants and teams to query runs, logs, credentials, memory, and streams through the same surfaces. | No response crosses tenant or unauthorized team scope; credential and memory access remain isolated. |
| 4.2 Webhook validation | Replay requests with invalid signatures, stale timestamps, duplicate delivery IDs, and burst traffic. | Invalid or stale requests reject before queueing, duplicates deduplicate, and floods throttle with auditable reasons. |
| 4.3 Security validation | Simulate forbidden-path diffs, prompt-injection content, secret findings, and repositories without required branch protection. | The run escalates on the registered security path, blocks unsafe output, and never reaches ordinary PR creation. |

These fixtures seed later implementation phases:

- Phase 4 adds budget and provider pause variants to the same runtime boundaries.
- Phase 5 ensures graph and agent configuration cannot disable these policies.
- Phase 7 promotes secret, branch-protection, and intake checks into CI and operational acceptance gates.

## Implementation Slice

This phase now includes a contract-level backend security slice under `backend/src/backend/security/` plus test coverage in `backend/tests/test_security_contracts.py`.

Implemented modules:

- `auth.py` maps normalized OIDC-style claims into `AuthContext` and evaluates tenant-, team-, and role-scoped authorization decisions.
- `credentials.py` enforces GitHub App preference and rotation-window blocking for overdue credentials.
- `webhook.py` verifies HMAC signatures, freshness windows, idempotency, and simple per-endpoint flood limits with auditable rejection reasons.
- `prompt.py` builds prompt envelopes, screens unsafe output markers, and enforces a role-based tool allowlist.
- `repository.py` evaluates protected paths, secret-like findings, branch protection, and signed-commit requirements before a run can continue toward PR creation.

Implementation boundaries:

- The slice is deliberately in-memory and synchronous for now so the trust model is executable without introducing premature identity-provider, Vault, Redis, or database coupling.
- These services are policy primitives. They do not replace later middleware, storage, or operator-facing audit implementations described in subsequent phases.
- The runtime success path from phase 1 remains unchanged. These checks prepare the security decisions that later webhook, auth, and PR paths will enforce directly.
