# STATUS

Last updated: 2026-04-18

## Overall status

LangGraph Dev Squad is in a pre-production state with substantial executable backend and frontend slices already implemented. The repository contains a working runtime simulation path, tested policy and persistence foundations, and an operator UI shell, but it is not yet 100% production-operational against the full scope described in `docs/PLAN.md`.

This document distinguishes between:

- implemented foundations that are already present in code and covered by the archived OpenSpec phases
- remaining work required before the system can be considered fully operational in production

## Macro items/specs already completed

The following macro areas are implemented as repository slices and have corresponding archived OpenSpec phases and test coverage.

### 1. Runtime SDD backbone

Status: Implemented foundation

Covered areas:

- `autonomous-ticket-flow`
- `runtime-artifact-lifecycle`
- `ticket-execution-state`
- `context-resolution-policy`

What exists now:

- planner-owned artifact flow before any repo-writing path
- readiness gate before coder execution
- bounded clarify, test, and review loops
- escalation sink validation
- pre-PR sync and PR path guard structure
- runtime simulation API for exercising the flow

### 2. Platform and execution foundations

Status: Implemented foundation

Covered areas:

- `deployment-topology`
- `sandbox-execution`
- `worker-queue-operations`

What exists now:

- queue and DLQ contracts
- weighted-fair dispatch logic
- worker drain and checkpoint semantics
- sandbox job template generation
- initial persistence and worker wiring abstractions

### 3. Security, tenancy, and access foundations

Status: Implemented foundation

Covered areas:

- `tenant-isolation-and-credentials`
- `oidc-rbac-access`
- `webhook-and-api-protection`
- `prompt-and-tool-safety`

What exists now:

- OIDC claim mapping and RBAC policy primitives
- webhook signature, freshness, idempotency, and rate-limit guards
- repository protection and forbidden-path evaluation
- prompt safety and tool policy enforcement
- credential policy primitives and rotation checks

### 4. LLM governance and metering foundations

Status: Implemented foundation

Covered areas:

- `model-catalog-and-token-caps`
- `provider-routing-and-failover`
- `budget-governance`
- `llm-metering-and-billing`

What exists now:

- model catalog and role token policies
- provider routing and failover logic
- atomic budget reservation semantics
- durable budget reservation cutover using PostgreSQL ledger rows plus Redis-backed atomic counters
- durable metering facts in PostgreSQL plus hourly rollups for export
- CSV export sourced from rollups with reconciliation coverage against raw facts
- contract tests for failover, budgeting, and settlement behavior

### 5. Config-driven runtime and admin control foundations

Status: Implemented foundation

Covered areas:

- `graph-configuration-runtime`
- `graph-shadow-mode`
- `config-versioning-and-rollback`
- `agent-configuration-governance`

What exists now:

- graph validation rules for protected workflow invariants
- versioned config and snapshot concepts
- rollback-safe snapshot pinning concepts
- shadow-mode evaluation primitives
- Postgres-backed control-plane components with tests

### 6. Operator UI foundations

Status: Implemented in degraded or foundational form

Covered areas:

- `admin-and-monitoring-ui`
- `visual-graph-editor`
- `pixel-art-control-room`
- `sprite-asset-management`
- `frontend-accessibility-and-localization`

What exists now:

- role-aware navigation
- dashboard, control room, interrupts, graph editor, and admin surfaces
- reduced-motion support and accessibility-first interaction baseline
- read-only graph visualization and validation feedback
- bundled sprites and English-only localization scaffolding

Important limitation:

- these UI specs are not yet complete at full production parity; several are intentionally in degraded mode

### 7. Observability, reliability, and release foundations

Status: Implemented foundation

Covered areas:

- `observability-and-incident-response`
- `service-level-objectives-and-alerting`
- `disaster-recovery-and-high-availability`
- `release-engineering-and-feature-flags`
- `quality-engineering-strategy`
- `data-retention-and-compliance-operations`

What exists now:

- observability catalog and incident primitives
- SLI/SLO evaluation logic
- release and rollback policy primitives
- resilience and retention policy foundations
- quality gate policy coverage

## Macro items that are partially complete but not production-ready

These areas exist in code, but are not yet complete enough to declare the product production-operational.

### Persistence cutover

Status: In progress

- Postgres and Redis-backed adapters exist
- the durable budget ledger cutover is now implemented
- the durable metering ledger cutover is now implemented, including hourly rollups and CSV export from rollups
- the persistence factory still defaults to in-memory implementations and selectively swaps real adapters by configuration
- model catalog, provider health, tenant-wide RLS completion, and the remaining production cutovers are still tracked by the open change `replace-in-memory-with-postgres-redis`

### Frontend productization

Status: In progress

- the frontend is functional as an operator shell
- live data is still represented by local sample data
- graph editing is still read-only
- sprite upload is still deferred
- localization is still English-only

### Infrastructure delivery

Status: Not complete

- the plan requires Helm-based Kubernetes deployment and production workload topology
- `helm/` is still a scaffold placeholder, so production deployment packaging is not complete

## Remaining work required for a 100% production-operational system

The following work is still required if the goal is full production readiness, not just a runnable repository.

### Tier 1 production blockers

These items block a true production-ready deployment and map directly to the remaining open OpenSpec changes and unresolved plan commitments.

- Complete `replace-in-memory-with-postgres-redis`
  - make Postgres and Redis the default operational backbone for runs, control plane, queue behavior, metering, and webhook persistence
  - remove remaining dependence on in-memory defaults for production paths

- Deliver Kubernetes-native deployment packaging
  - implement the connected and `air_gapped` Helm charts
  - validate HPA, probes, resource quotas, sandbox runtime settings, and production topology

- Complete `air-gapped-deployment-profile`
  - enforce no external LLM egress
  - validate self-hosted provider routing and deployment constraints

- Complete `jira-webhook-replay-and-rate-limit-hardening`
  - finish production webhook replay, abuse, and intake hardening beyond the current foundation

- Complete `github-app-pat-onboarding-mechanics`
  - production GitHub App onboarding flow
  - enforce GitHub App as default and PAT as explicit restricted fallback

- Complete `credential-rotation-sla-and-break-glass`
  - operationalize 90-day rotation, alerts, and dual-control emergency procedures

- Complete `supply-chain-and-admission-controller`
  - SBOM, signing, provenance, and cluster admission enforcement for unsigned artifacts

- Complete `progressive-delivery-and-feature-flag-kill-switches`
  - canary rollout, automated rollback, and kill switches for high-risk runtime capabilities

- Complete `api-versioning-and-openapi-diff-gate`
  - formal `/v1` compatibility governance
  - schema diff gates in CI

- Complete `data-retention-deletion-and-dpa-compliance`
  - tenant deletion cascade, retention automation, compliance documentation, and DPA acknowledgment path

- Complete `public-status-page-and-incident-runbooks`
  - public status communication, runbook coverage, and operational incident response maturity

- Complete `chaos-fuzz-and-prompt-regression-testing-program`
  - chaos, fuzz, and prompt regression coverage required by the production test strategy

### Tier 2 parity work still missing for full plan completion

These items may have documented degraded paths for GA, but they are still missing if the target is 100% implementation of the plan.

- Complete `billing-rate-card-reconciliation`
  - hourly rollups, versioned rate cards, export maturity, nightly reconciliation

- Finish the full visual graph editor experience
  - node, edge, route, and interrupt CRUD
  - activation and shadow-mode UX beyond the current read-only validation shell

- Finish sprite asset management
  - upload flow, role/state mapping, and persistence beyond bundled assets only

- Finish full pixel-art control-room parity
  - real-time integration, animation richness, and production-grade polish

- Finish localization parity
  - deliver the Spanish locale and broader localization completeness

### Optional extension still pending

- `optional-internal-rag-via-pgvector`
  - optional capability, not required for minimum production operation
  - still pending if the product target includes the full optional extension set

## Practical production-readiness summary

If the question is "can this repo run meaningful slices today?", the answer is yes.

If the question is "can this system be declared fully production-operational for enterprise self-hosted customers as described in `docs/PLAN.md`?", the answer is no, not yet.

At a macro level:

- completed: core runtime, policy, governance, control-plane, and UI foundations
- partially complete: persistence cutover, frontend productization, operational packaging
- still required: deployment packaging, production hardening, supply-chain enforcement, progressive delivery, compliance operations, public incident tooling, and the remaining quality program

## Current validation snapshot

Recent local validation in this repository showed:

- backend tests passing: 50 passed, 16 skipped
- frontend tests passing
- frontend production build passing

This supports the conclusion that the codebase is executable and actively advancing, but not yet at full production-operational scope.
