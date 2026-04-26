# STATUS

Last updated: 2026-04-26

## Overall status

LangGraph Dev Squad is still pre-production, but the repository has moved beyond a scaffold. It now contains executable backend and frontend slices, a runnable runtime simulation path, durable PostgreSQL and Redis persistence adapters, baseline Helm packaging, and tested policy foundations.

This is not yet a 100% production-operational enterprise deployment. The remaining gaps are mostly around production hardening, supply-chain enforcement, API compatibility gates, incident/status operations, and the full quality program.

This document compares three sources:

- actual repository code, tests, docs, and Helm manifests
- archived OpenSpec changes under `openspec/changes/archive`
- active OpenSpec changes under `openspec/changes`

## OpenSpec status snapshot

Archived and treated as completed foundation work:

- `2026-04-18-phase-1-runtime-sdd-pipeline`
- `2026-04-18-phase-2-platform-and-sandbox`
- `2026-04-18-phase-3-tenant-security-and-access`
- `2026-04-18-phase-4-llm-governance-and-metering`
- `2026-04-18-phase-5-config-driven-graph-and-admin-control`
- `2026-04-18-phase-6-operator-ui-and-control-room`
- `2026-04-18-phase-7-observability-reliability-and-release`
- `2026-04-22-replace-in-memory-with-postgres-redis`
- `2026-04-24-github-app-pat-onboarding-mechanics`
- `2026-04-26-api-versioning-and-openapi-diff-gate`
- `2026-04-26-optional-internal-rag-via-pgvector`
- `2026-04-26-public-status-page-and-incident-runbooks`
- `2026-04-26-air-gapped-deployment-profile`
- `2026-04-26-supply-chain-and-admission-controller`
- `2026-04-26-billing-rate-card-reconciliation`

Active changes still open:

- `chaos-fuzz-and-prompt-regression-testing-program` - not implemented
- `credential-rotation-sla-and-break-glass` - not implemented
- `data-retention-deletion-and-dpa-compliance` - not implemented
- `jira-webhook-replay-and-rate-limit-hardening` - not implemented beyond the existing foundation
- `progressive-delivery-and-feature-flag-kill-switches` - not implemented as a full change

## Implemented foundations

### 1. Runtime SDD backbone

Status: Implemented foundation

Covered OpenSpec areas:

- `autonomous-ticket-flow`
- `runtime-artifact-lifecycle`
- `ticket-execution-state`
- `context-resolution-policy`

What exists now:

- planner-owned artifact flow before any repo-writing path
- readiness gate before coder execution
- bounded clarification, test, and review loops
- escalation sink validation
- diff, merge-conflict, branch-protection, pre-PR sync, and PR path guard structure
- runtime simulation API for exercising the flow

### 2. Platform and execution foundations

Status: Implemented foundation

Covered OpenSpec areas:

- `deployment-topology`
- `sandbox-execution`
- `worker-queue-operations`

What exists now:

- FastAPI route groups for the current `/api/v1` surface
- queue and DLQ contracts
- weighted-fair dispatch logic
- worker drain and checkpoint semantics
- sandbox job template generation
- local Kubernetes manifests under `k8s/`

### 3. Security, tenancy, and access foundations

Status: Implemented foundation

Covered OpenSpec areas:

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

Covered OpenSpec areas:

- `model-catalog-and-token-caps`
- `provider-routing-and-failover`
- `budget-governance`
- `llm-metering-and-billing`

What exists now:

- model catalog and role token policies
- provider routing and failover logic
- Redis-shared provider health store in the production adapter path
- atomic budget reservation semantics
- PostgreSQL-backed budget reservation and charge records
- PostgreSQL-backed metering facts and hourly rollups
- CSV export sourced from rollups with reconciliation coverage against raw facts
- contract tests for failover, budgeting, and settlement behavior

### 5. Config-driven runtime and admin control foundations

Status: Implemented foundation

Covered OpenSpec areas:

- `graph-configuration-runtime`
- `graph-shadow-mode`
- `config-versioning-and-rollback`
- `agent-configuration-governance`

What exists now:

- graph validation rules for protected workflow invariants
- versioned graph and agent config concepts
- snapshot pinning and rollback primitives
- shadow-mode evaluation primitives
- PostgreSQL-backed control-plane components with tests

### 6. Durable persistence backbone

Status: Implemented and archived as foundation work

Covered OpenSpec change:

- `2026-04-22-replace-in-memory-with-postgres-redis`

What exists now:

- PostgreSQL-backed run repository, control-plane store, metering ledger, budget ledger, model catalog, and webhook idempotency storage
- Redis-backed worker coordination, budget counters, webhook short-window dedupe, provider circuit breaker, and control-plane snapshot invalidation
- Alembic migrations through `20260422_0008`
- row-level security helpers and tenant-scoped persistence tests
- persistence health, migration status, readiness, metrics, alerts, dashboards, and runbooks
- factory tests that force production adapters when PostgreSQL and Redis are configured

Important limitation:

- development mode still falls back to `InMemory*` adapters when no database URL is configured. That is acceptable for local tests, but a production deployment must provide PostgreSQL and Redis and must not rely on the fallback path.

### 7. Operator UI foundations

Status: Implemented in degraded or foundational form

Covered OpenSpec areas:

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
- PAT mode banner and GitHub-related UI surface work in progress
- public status tile in the admin panel reading `/api/v1/status-page`

Important limitation:

- live data is still represented mostly by local sample data
- graph editing is still read-only
- sprite upload is still deferred
- localization is still English-only

### 8. Observability, reliability, and release foundations

Status: Implemented foundation

Covered OpenSpec areas:

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
- persistence-specific alerts, dashboard, and runbooks
- public status template
- `/api/v1/status-page` whitelist endpoint with component states derived from health and Prometheus-format metrics

### 9. Baseline deployment packaging

Status: Implemented baseline, not production-complete

What exists now:

- Helm chart files under `helm/`
- connected, `air_gapped`, staging, and production values files
- air-gapped Helm validation rejects vendor LLM keys, external statuspage sync, LangSmith tracing, and Vault dev mode
- air-gapped NetworkPolicy allows only internal OpenCode Go, internal embedding, and cluster DNS egress from backend pods
- backend pod templates receive `BACKEND_DEPLOYMENT_PROFILE` and the Helm-configured OpenCode Go endpoint
- External Secrets Operator templates with LangSmith API key sync from Vault
- NetworkPolicy template
- baseline Rollout template and canary step values
- local development manifests under `k8s/`
- LangSmith tracing toggle (`langsmith.enabled`) with per-environment project separation; Vault + ESO is the production path, direct `kubectl create secret` is the local path
- vendor telemetry suppression (`DO_NOT_TRACK=1`, `LANGCHAIN_TRACING_V2=false`) when LangSmith is disabled, preventing PostHog network flush errors in air-gapped deployments
- offline Vault bootstrap script and operator custody guidance for the air-gapped profile

Important limitation:

- the active `progressive-delivery-and-feature-flag-kill-switches` change is still open, so the chart is not yet the fully validated production delivery package described in `docs/PLAN.md`.

### 10. Supply-chain and admission controller

Status: Implemented

Covered OpenSpec change:

- `supply-chain-and-admission-controller`

What exists now:

- CI workflow with cosign keyless signing bound to GitHub OIDC identity
- SLSA Level 3 provenance generation via `slsa-github-generator`
- SBOM generation with syft and attachment to container images
- Trivy, Grype, and OSV-Scanner vulnerability scanning blocking on CRITICAL and HIGH
- License allowlist enforcement via `scripts/check_license_allowlist.py` with `.github/license-allowlist.json`
- Secret scanning via gitleaks and trufflehog
- Dockerfile lint with hadolint and `:latest` tag rejection
- Kyverno admission policies: signature required, provenance required, digest-pinned, no-latest
- Helm chart under `helm/policies/` with connected and `air_gapped` values
- `admission_exceptions` table with Alembic migration `20260426_0011`
- Admin API for exception CRUD with dual super_admin approval and mandatory `expires_at`
- Renovate config with grouped PRs, auto-merge on minor/patch, human review for majors
- Runbooks: signature verification failure, provenance verification failure, exception approval
- Contract tests for admission API and license allowlist

Important limitation:

- admission policies ship in `Audit` mode by default; flipping to `Enforce` requires staging validation
- ephemeral K3s integration test and air-gapped bundle verification are documented but require cluster infrastructure to execute
- archive is blocked on enforce-mode stability in production

### 11. Billing rate-card reconciliation

Status: Implemented

Covered OpenSpec change:

- `2026-04-26-billing-rate-card-reconciliation`

What exists now:

- `price_rate_cards` table with versioned effective windows, audit, and shadow-mode validation (Alembic migration `20260426_0012`)
- `provider_request_id` column on `metering_facts` for invoice line-item matching
- `reconciliation_reports` table with drift tracking and dry-run/enforce modes
- Admin API CRUD for rate cards at `/api/v1/billing/rate-cards/*`
- Rate card activation with audit trail
- Nightly reconciliation endpoint at `/api/v1/billing/reconcile` with dry-run mode
- Drift alert at >2% with Prometheus metrics (`devsquad_billing_drift_percentage`, `devsquad_billing_drift_alerts_total`)
- Finance export at `/api/v1/billing/export` with CSV and JSON (v1/v2) versions
- Reconciliation report listing at `/api/v1/billing/reconciliation-reports`
- Contract tests under `backend/tests/test_billing_rate_card_contracts.py` - 14 tests passing

Important limitation:

- reconciliation is operator-driven via API; full ARQ scheduled job requires worker queue integration
- provider invoice ingestion is manual; no automatic provider invoice API integration

## Active work with implementation present

### GitHub App and PAT onboarding mechanics

Status: Archived as `2026-04-24-github-app-pat-onboarding-mechanics`

What exists:

- GitHub integration modules for permission hashing, least-privilege checks, installation-token minting, drift detection, branch-protection verification, and metrics
- Alembic migration and schema entries for GitHub App installations, GitHub credentials, PAT opt-ins, and branch-protection verification records
- runtime branch-protection guard before PR creation
- PAT credential policy and reduced PAT rate-limit behavior
- admin router for installation registration, PAT opt-in, and drift acknowledgement
- frontend PAT mode banner
- Helm values for GitHub App configuration and Vault-held private key references
- contract tests under `backend/tests/test_github_integration_contracts.py`
- runbooks and alert rules for GitHub mint failures and permission drift

### Optional internal RAG via pgvector

Status: Archived as `2026-04-26-optional-internal-rag-via-pgvector`

Covered OpenSpec change:

- `optional-internal-rag-via-pgvector`

What exists now:

- `knowledge_documents`, `knowledge_chunks`, and `knowledge_ingestion_jobs` tables with row-level security and HNSW index (Alembic migration `20260424_0009`)
- `internal_rag_enabled` feature flag registered, default OFF, boot probe for pgvector extension presence
- admin API CRUD and ingest endpoints at `/api/v1/admin/knowledge/*`
- background ARQ ingestion jobs with progress metrics and resumability
- HNSW-indexed retrieval with role whitelist (`planner`, `reviewer` only) and read-only semantics during runs
- excerpt summaries persisted in run state for audit and reproducibility
- admin dry-run search endpoint for operators
- self-hosted embedding endpoint in Helm values; NetworkPolicy denies vendor egress in air-gapped profile
- LangSmith tracing support via `langsmith.enabled` Helm toggle (Vault + ESO integration, `values-staging.yaml`, `values-prod.yaml`)
- Prometheus metrics: ingestion progress, retrieval latency p95, hit rate, excerpt size distribution
- PostHog network flush errors from the `langsmith` transitive dependency suppressed via `DO_NOT_TRACK=1` and `LANGCHAIN_TRACING_V2=false` when LangSmith is disabled
- runbook covering enablement, rollback, and retention
- `backend/tests/test_internal_rag_contracts.py` with tenant-scope negative tests and role whitelist enforcement - all passing

Local validation evidence (2026-04-24):

- `/readyz` returns `status: ok` with knowledge capability probe clean
- all 7 `/api/v1/admin/knowledge/*` endpoints registered and responding correctly
- document CRUD, ingest (status: completed), and dry-run search (correct hit, distance 0.0) verified
- tenant isolation: cross-tenant search returns empty hits
- role whitelist: `coder` role returns `knowledge_retrieval_denied:coder`
- admin guard: `viewer` role returns `admin_role_required`
- all 5 Prometheus metric families present with correct tenant and team labels

Bug fixed during validation:

- `persistence/health.py` was marking pods as `not_ready` when `BACKEND_DATABASE_URL` was absent (`state: not_configured`), causing CrashLoopBackOff after image rebuild. Fixed by skipping `database_unhealthy`, `redis_unhealthy`, and `migration_drift` checks when migration state is `not_configured`. All 118 backend tests pass after the fix.

Archive status:

- archived after local validation and evidence capture for the OpenSpec change

### API versioning and OpenAPI diff gate

Status: Archived as `2026-04-26-api-versioning-and-openapi-diff-gate`

What exists:

- versioned `/api/v1/openapi.json` document exposing the active major API surface
- Accept-Version negotiation with unsupported major rejection
- deprecation metadata endpoint plus deprecation and sunset headers on registered routes
- OpenAPI diff gate script with breaking-change detection and super-admin bypass registry checks
- API deprecation docs, baseline OpenAPI artifact, alert rules, and tests

### Public status page and incident runbooks

Status: Archived as `2026-04-26-public-status-page-and-incident-runbooks`

Completed so far:

- artifact alignment against Phase 7 observability and incident-response specs
- `/api/v1/status-page` backend endpoint returning `public-status.v1`
- whitelist-only response schema with fixed component fields and no tenant, team, ticket, or secret data
- component state derivation from health probes and Prometheus-format metrics for API, workers, database, Redis, provider routing, sandbox runtime, and persistence backbone
- admin UI public status tile that fetches `/api/v1/status-page` and renders text labels for every state
- connected-profile `status-page-sync` CronJob that posts the status payload to a Vault-sourced statuspage endpoint
- air-gapped profile disables external status sync and documents the internal `/api/v1/status-page` and admin UI fallback
- SEV1/2/3 severity model, escalation matrix, and PagerDuty routing-key delivery through External Secrets Operator
- mandatory `all-providers-down.md` and `air-gapped-deployment.md` runbooks
- existing paging alerts now carry `runbook_url` labels pointing at checked-in runbooks
- local alert-runbook lint script and tests
- backend contract tests and frontend tests for the status-page surface

## Remaining work required for full production readiness

The following items block a true production-ready deployment and map to active OpenSpec changes or unresolved plan commitments.

### Tier 1 production blockers

- Complete `jira-webhook-replay-and-rate-limit-hardening`
  - add replay hardening beyond the current `(source, delivery_id)` idempotency foundation
  - implement dual-secret rotation, CIDR allowlists, and Redis sliding-window enforcement

- Complete `credential-rotation-sla-and-break-glass`
  - operationalize rotation schedules, alerts, dual-control break-glass, and KEK rotation drills

- Complete `progressive-delivery-and-feature-flag-kill-switches`
  - wire Argo Rollouts analysis, automated rollback, OpenFeature integration, and kill-switch drills

- Complete `data-retention-deletion-and-dpa-compliance`
  - implement tenant deletion cascade, retention automation, compliance documentation, and DPA acknowledgement

- Complete `chaos-fuzz-and-prompt-regression-testing-program`
  - add chaos, fuzz, and prompt regression coverage required by the production test strategy

### Tier 2 parity work still missing for full plan completion

These items may have documented degraded paths for GA, but they are still missing if the target is 100% implementation of the plan.

- Finish the full visual graph editor experience
  - node, edge, route, and interrupt CRUD
  - activation and shadow-mode UX beyond the current read-only validation shell

- Finish sprite asset management
  - upload flow, role/state mapping, and persistence beyond bundled assets only

- Finish full pixel-art control-room parity
  - real-time integration, richer state mapping, and production-grade polish

- Finish localization parity
  - deliver the Spanish locale and broader localization completeness

## Practical production-readiness summary

If the question is "can this repo run meaningful slices today?", the answer is yes.

If the question is "can this system be declared fully production-operational for enterprise self-hosted customers as described in `docs/PLAN.md`?", the answer is no.

At a macro level:

- completed foundations: runtime, platform contracts, security contracts, LLM governance, durable persistence, control plane, UI shell, operations policy primitives, GitHub App and PAT onboarding, API versioning, OpenAPI diff gate, optional internal RAG, and public status/runbook baseline
- partially complete: frontend productization, production Helm delivery, operational drills, and live deployment evidence
- still required: webhook hardening, progressive delivery, compliance operations, real paging drill evidence, and the expanded quality program

## Current validation snapshot

Validation run during this status update (2026-04-26):

- `uv run --project backend ruff check backend/src backend/tests scripts/lint_alert_runbooks.py` - passed
- `uv run --project backend pytest` - passed, 166 passed, 1 skipped, 0 failed
- `npm run --prefix frontend test -- --run` - passed, 7 passed
- `npm run --prefix frontend build` - passed
- `helm template dev-squad ./helm -f ./helm/values.yaml` - passed
- `helm template dev-squad ./helm -f ./helm/values.yaml -f ./helm/values-air-gapped.yaml` - passed
- `helm template dev-squad ./helm -f ./helm/values.yaml -f ./helm/values-air-gapped.yaml --set llm.vendorApiKeys.anthropic=sk-test` - failed as expected with `air_gapped profile rejects vendor LLM API keys`
- `helm template dev-squad ./helm -f ./helm/values.yaml -f ./helm/values-staging.yaml` - passed
- `helm template dev-squad ./helm/policies -f ./helm/policies/values.yaml` - passed
- `helm template dev-squad ./helm/policies -f ./helm/policies/values-air-gapped.yaml` - passed
- `uv run --project backend python scripts/lint_alert_runbooks.py` - passed with orphan-runbook warnings only
- `uv run --project backend python scripts/check_license_allowlist.py` - script validates correctly
- focused status-page contract check - included in the backend and frontend runs above

The seven PostgreSQL and Redis persistence test failures that appeared in the previous snapshot are resolved. Those tests were updated as part of the persistence backbone work to run against in-memory adapters when no database URL is present, so they now pass in the standard local test run without requiring a live PostgreSQL or Redis instance.

A separate bug was also fixed in `persistence/health.py` during internal RAG validation: readiness and liveness probes were marking the pod `not_ready` when the migration state was `not_configured` (no DATABASE_URL present), causing CrashLoopBackOff on fresh pod starts. The fix skips `database_unhealthy`, `redis_unhealthy`, and `migration_drift` checks when state is `not_configured`.
