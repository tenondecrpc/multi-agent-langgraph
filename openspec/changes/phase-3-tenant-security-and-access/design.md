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
