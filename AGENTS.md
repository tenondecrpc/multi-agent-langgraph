# AGENTS.md

Guidelines for agentic coding agents operating in this repository.

## Instruction Source

`AGENTS.md` is the single source of truth for repository instructions used by agent harnesses (Claude Code, Codex, OpenCode, and similar).

`openspec/config.yaml` is the single source of truth for Spec-Driven Development artifacts. It is the constitution that governs OpenSpec proposals, specs, design, and tasks.

`AGENTS.md` and `openspec/config.yaml` must stay synchronized and express the same product, deployment, architecture, workflow, and guardrail rules. If they disagree, treat `openspec/config.yaml` as authoritative for SDD artifacts and reconcile `AGENTS.md` in the same change.

`CLAUDE.md` is a thin bootstrap that defers to `AGENTS.md` and must not duplicate repository rules.

## Language

All agent communication and written outputs in this repository must be in English. This includes OpenSpec proposals, specs, design docs, task lists, code comments, commit messages, and PR descriptions.

## Formatting

These formatting rules apply to all agent-written output in this repository, including Codex, OpenCode, and Claude Code.

Use ASCII punctuation by default.

Do not use em dashes (`—`) or en dashes (`–`) in prose, bullet lists, headings, commit messages, plans, or code comments.

Always use the plain ASCII hyphen (`-`) instead.

Preferred example:

- `Planner artifact - feature spec and clarification notes`

## Project

LangGraph Dev Squad is a self-hosted enterprise multi-agent system that takes Jira tickets, iterates on code until tests pass, and opens GitHub pull requests. It runs inside customer-owned Kubernetes with tenant and team isolation, horizontal scaling, auditability, and production-grade observability. There is no vendor-operated SaaS control plane and no cross-customer data plane. Connected and air-gapped deployment profiles are both first-class.

**Pipelines**:

- Ticket pipeline: Jira webhook -> FastAPI -> ARQ queue -> LangGraph graph (`planner` -> `coder` -> `tester` -> `reviewer` -> `pr_creator`) -> GitHub PR
- Artifact pipeline: `constitution -> feature_spec -> clarification_notes -> implementation_plan -> task_list -> implement -> test -> review -> pre_pr_sync -> pr_creator`
- Config pipeline: admin UI or API -> versioned config in PostgreSQL -> shadow-mode validation -> active runtime graph

Do not collapse the ticket pipeline and the artifact pipeline into a single source. Repo-writing cannot begin until `spec_ready_for_implementation` is true and a task list exists.

## Two SDD Layers

This repository operates at two distinct Spec-Driven Development layers. They share vocabulary (`constitution`, `spec`, `plan`, `tasks`) but are not interchangeable.

- **Build-time SDD (OpenSpec)**: governs how this repository evolves. It is used by humans and agent harnesses (Claude Code, Codex, OpenCode) when proposing, designing, implementing, and archiving changes to this product. Its constitution is `openspec/config.yaml`. Its artifacts live as Markdown under `openspec/` and follow the propose -> explore -> apply -> archive lifecycle via the OpenSpec skills.
- **Run-time SDD (SpecKit-style)**: governs how the LangGraph Dev Squad resolves each Jira ticket at runtime. It is used by the `planner`, `coder`, `tester`, `reviewer`, and `pr_creator` agents operating inside a customer-owned deployment. Its per-ticket constitution is derived from the target customer repo plus tenant configuration. Its artifacts are persisted in PostgreSQL checkpoints, memory, and state, not as files in `openspec/`.

Do not conflate them:

- OpenSpec artifacts never flow into the runtime ticket pipeline as agent input.
- SpecKit-style runtime artifacts (feature spec, clarification notes, plan, tasks) produced per Jira ticket are never committed to `openspec/` in this repository.
- Both layers share the same protected invariants (repo-write gate, mandatory test and review before PR creation, break-glass-only human approval). When you write OpenSpec artifacts that describe the runtime chain, you are specifying behavior for the run-time layer, not executing it.

When in doubt: changes to this repository go through OpenSpec. Changes to customer code produced by the deployed product go through the runtime SpecKit-style chain.

## Repository Status

This repository is in early implementation. Executable backend and frontend slices now exist under `backend/` and `frontend/`. Human-readable operator and status documentation now exists under `docs/`, machine-readable contracts live under `contracts/`, deployable operational artifacts live under `operations/`, and `helm/` remains a scaffold.

Scaffold targets remain:

- `backend/` - FastAPI app, ARQ workers, LangGraph graph, integrations
- `frontend/` - Vite + React + TypeScript admin and monitoring UI
- `helm/` - Helm charts for Kubernetes deployment (connected and `air_gapped` profiles)
- `contracts/` - Machine-readable API contracts and approval registries
- `operations/` - Deployable operational artifacts such as alert rules and dashboards
- `docs/` - Human-readable operator, integrator, and developer documentation

Use `uv` for Python dependency management, environment synchronization, and Python command execution.

Current backend commands from the repository root:

- Sync dependencies: `uv sync --project backend --dev`
- Lint: `uv run --project backend ruff check backend/src backend/tests`
- Test: `uv run --project backend pytest`

Current frontend commands from the repository root:

- Install dependencies: `npm install --prefix frontend`
- Test: `npm run --prefix frontend test -- --run`
- Build: `npm run --prefix frontend build`

## Deployment Model

- Self-hosted only inside customer-owned infrastructure.
- No vendor-operated SaaS control plane.
- No cross-customer data plane. "Multi-tenancy" only means teams, business units, and projects inside one customer-owned deployment.
- Customer-owned secrets, data stores, object storage, and LLM provider accounts are mandatory.
- Air-gapped deployment is a first-class supported profile.

## Core Architecture

- LangGraph orchestrates `planner`, `coder`, `tester`, `reviewer`, and `pr_creator` roles.
- FastAPI handles webhooks, status APIs, auth callback, and admin APIs.
- ARQ and Redis handle queueing, pub/sub, and idempotency.
- PostgreSQL is the durable system of record for checkpoints, memory, config, audit, and metering.
- Vite + React + TypeScript power the monitoring and admin UI.
- Sandboxed code execution runs in Kubernetes Jobs hardened with gVisor.
- Optional internal knowledge retrieval uses `pgvector` in PostgreSQL, not a separate datastore.

## Core Stack

- Orchestration: LangGraph `StateGraph`, `langgraph-checkpoint-postgres`, `langgraph.store.postgres`
- API and workers: FastAPI, ARQ
- Python packaging and environments: `uv`
- Persistence and queues: PostgreSQL 16 HA, Redis 7 Cluster, optional `pgvector`
- Frontend: Vite, React, TypeScript
- Sandboxing: Kubernetes 1.30+, gVisor
- Integrations: Jira Python client, PyGithub, GitPython, `authlib` OIDC, GitHub App
- Secrets and config: HashiCorp Vault, External Secrets Operator, versioned PostgreSQL config
- Observability: OpenTelemetry, LangSmith, Prometheus, Alertmanager, Grafana, Loki, Tempo
- Delivery and control: Helm, Kustomize, Argo Rollouts, OpenFeature with Unleash or LaunchDarkly
- Security and supply chain: `gitleaks`, `trufflehog`, `syft`, `cosign`, Trivy, Grype, OSV-Scanner

## Execution Model

- Autonomous-first Spec-Driven Development is the default v1 path.
- Canonical artifact chain: `constitution -> feature_spec -> clarification_notes -> implementation_plan -> task_list -> implement -> test -> review -> pre_pr_sync -> pr_creator`.
- No repo-writing step may run until `spec_ready_for_implementation` is true and a task list exists.
- Human approval is break-glass only for exception paths such as `security_review`, merge conflicts, budget exhaustion, policy violations, or unresolved ambiguity after max autonomous spec iterations.
- Constitution, spec, clarification, plan, tasks, and review context must stay persisted in state and checkpoints.

## Design Principles

- Local-first context resolution order: Jira -> repo -> checkpoints and memory -> optional internal knowledge -> first-party docs and APIs -> external research fallback.
- CLI-first for operational integrations when practical; prefer official CLIs and native command surfaces.
- Least-privilege tool access per role is mandatory.
- Runtime graph is config-driven and editable, but protected v1 workflow invariants cannot be bypassed.

## Tier 1 Non-Negotiables

- Parallel ticket processing across horizontally scaled workers is mandatory.
- Kubernetes-native deployment is mandatory: Helm, HPA, health probes, and gVisor sandboxes are required.
- Multi-tenancy is mandatory with tenant and team isolation across credentials, data, memory, budgets, and queue behavior.
- OIDC authentication and four-tier RBAC are mandatory; backend enforcement is authoritative.
- LLM budget governance is mandatory with race-free reservations and per-ticket and per-team caps.
- Provider failover is mandatory with a Redis-shared circuit breaker and air-gapped-safe fallback behavior.
- Sandbox hardening is mandatory: gVisor, per-tenant namespaces, egress controls, resource quotas, non-root execution.
- Envelope encryption and external KMS or Vault integration are mandatory.
- GitHub App is the default integration path; PAT usage is explicit opt-in and more restricted.
- Webhook security is mandatory: HMAC verification, timestamp freshness, idempotency, and rate limiting.
- Merge conflict detection before PR creation is mandatory.
- Diff size guard is mandatory; oversized diffs must split or escalate instead of flowing through blindly.
- Forbidden-path writes are mandatory to block: protected branches, CI config, infra, Dockerfiles, secrets, and CODEOWNERS-class files.
- Signed commits and branch protection verification are mandatory.
- Prompt injection defenses and secret scanning are mandatory on every relevant path.
- Supply chain security is mandatory: SBOM, signing, provenance, and admission enforcement.
- Configuration must be stored in PostgreSQL with versioning, audit trail, rollback, and shadow-mode validation.
- Schema changes must use expand/contract migration discipline with reversibility tests.
- Observability is mandatory: structured logs, metrics, traces, health probes, dashboards, and alerting.
- SLOs, burn-rate alerting, and error-budget policy are mandatory.
- Disaster recovery is mandatory with backups, restore drills, and defined RPO and RTO.
- Progressive delivery with automated rollback is mandatory.
- Rate limiting and weighted-fair queueing are mandatory.
- Feature-flag kill switches are mandatory for high-risk runtime capabilities.
- Public API versioning and diff gates are mandatory.
- Dead letter queue support is mandatory.
- Data retention, deletion, and DPA acknowledgement are mandatory.
- Graceful shutdown to checkpoint boundaries is mandatory.
- Credential rotation SLA and dual-control break-glass are mandatory.
- Both connected and `air_gapped` deployment profiles are mandatory.
- Comprehensive testing is mandatory: unit, integration, E2E, chaos, fuzz, and prompt regression.
- Public status communication and incident runbooks are mandatory.

## Tier 2 Goals With Allowed Degradation

- Spec-driven artifact lifecycle aims for full autonomous clarify loops; acceptable degradation is single-pass clarification with escalation on unresolved ambiguity.
- Visual graph editor aims for full node, edge, route, and interrupt CRUD; acceptable degradation is read-only visualization plus JSON config import and export.
- Custom sprite upload aims for admin upload and role and state mapping; acceptable degradation is bundled sprites only and upload returning `501`.
- Pixel-art control room aims for full-fidelity office scene; acceptable degradation is a functional reduced-motion pixel-art skin.
- Billing export aims for hourly rollups plus rate-card reconciliation; acceptable degradation is hourly rollups plus CSV export only.
- Internationalization aims for full Spanish locale; acceptable degradation is English-only with extraction infrastructure ready.
- Optional internal RAG via `pgvector` may stay disabled at GA; if enabled it must remain tenant-scoped, read-only during ticket execution, and reuse PostgreSQL.
- WCAG 2.1 AA end-to-end is the target; the non-negotiable subset is no color-only state, keyboard reachability of all interactive elements, `prefers-reduced-motion` support, and AA contrast on all text.

## Protected Workflow Invariants

- Any repo-writing path must start from planner-owned SDD artifacts.
- No repo-writing node may run until `spec_ready_for_implementation` is true and a task list exists.
- Any path that can reach PR creation must traverse implementation, tests, diff guard, review approval, and pre-PR sync.
- Every failure terminal path must map to an explicit escalation reason and a registered escalation sink.
- Human approval is allowed only as break-glass control on exception paths; the normal success path cannot require manual approval.

## Guardrails

- Do not propose or implement vendor-hosted control planes or any cross-customer data plane.
- Do not introduce a new production datastore for checkpoints, memory, config, audit, metering, or optional internal knowledge retrieval. Extend PostgreSQL (with `pgvector` when RAG is enabled) instead.
- Do not allow any repo-writing node to run before `spec_ready_for_implementation` is true and a task list exists.
- Do not route the normal success path through human approval. Interrupts are break-glass only.
- Do not bypass the mandatory chain on any path that can reach PR creation: implementation -> tests -> diff size guard -> forbidden-path guard -> review approval -> pre-PR sync.
- Do not weaken Tier 1 non-negotiables. A proposal that weakens a Tier 1 rule is invalid unless it is explicitly framed as amending `openspec/config.yaml` itself.
- Do not write to protected branches, CI config, infra, Dockerfiles, secrets, or CODEOWNERS-class files from agent code paths; the forbidden-path guard must block these.
- Do not store credentials in application config, environment variables committed to Git, frontend bundles, or logs. All secrets flow through Vault or External Secrets Operator with envelope encryption.
- Do not special-case the air-gapped profile after the fact. Every feature must reason about connected and `air_gapped` deployment from the design stage.
- Treat changes to Helm values, gVisor policy, network policies, RBAC, OIDC configuration, DB migrations, feature-flag kill switches, and graph escalation sinks as high-risk and call them out explicitly.
- Avoid designs that grant any agent more privilege than its role boundary requires.

## OpenSpec Artifact Rules

These mirror the `rules` block in `openspec/config.yaml`. When drafting artifacts, follow the rules for the artifact type being produced.

### Proposal

- Treat `openspec/config.yaml` as the constitution baseline.
- State whether the change touches Tier 1 non-negotiables, Tier 2 degradable goals, or an optional extension.
- Include non-goals, operational impact, risk, and rollback or degradation strategy for any risky change.
- Do not propose vendor-hosted control planes, cross-customer shared data planes, or weaker isolation and security tradeoffs.
- Any proposal that changes graph execution must preserve autonomous-first operation and break-glass-only interrupts on the success path.
- Any proposal that weakens a Tier 1 rule is invalid unless it is explicitly framed as changing the constitution itself.

### Specs

- Include explicit requirements, acceptance criteria, edge cases, and non-goals.
- Preserve self-hosted-only deployment, customer-owned data and secrets, and single-customer infrastructure boundaries.
- Preserve tenant and team isolation, least-privilege tool governance, local-first context resolution, and PostgreSQL-backed config and state.
- If repo-writing behavior is in scope, state the repo-write gate explicitly: no write before `spec_ready_for_implementation` is true and the task list exists.
- If UI is in scope, include accessibility requirements for keyboard reachability, no color-only state, `prefers-reduced-motion`, and AA text contrast.
- If graph or runtime behavior is in scope, preserve config-driven graph invariants, mandatory review, test, and pre-PR sync guards, and explicit escalation paths.
- If security or operations are in scope, include observability, rollback, auditability, and failure-mode requirements directly in the spec.

### Design

- Reuse and extend the architecture described in the constitution instead of inventing parallel systems.
- Keep configuration versioned, auditable, rollbackable, and compatible with PostgreSQL-backed config plus shadow mode.
- Preserve protected workflow invariants: SDD readiness before repo write, mandatory test and review before PR creation, and a registered escalation sink on failure paths.
- Document enforcement points, failure modes, observability, and rollback for security-sensitive or tenant-boundary changes.
- Optional capabilities must remain feature-flagged, tenant-scoped, and disabled by default unless the constitution says otherwise.
- Do not introduce a new production datastore for optional internal knowledge retrieval; use PostgreSQL plus `pgvector` when that capability is enabled.
- Avoid designs that grant any agent more privilege than its role boundary requires.

### Tasks

- Break work into small, ordered, testable tasks with explicit verification steps.
- Put artifact generation and refinement before implementation, and implementation before tests, review, and release actions.
- Include tests, observability, security or policy validation, and docs or config updates whenever applicable.
- If a Tier 2 capability ships in degraded form, include a follow-up parity task tied to the allowed degradation path in the constitution.
- Do not schedule repo-writing implementation tasks before the relevant spec, plan, and task artifacts are complete.

## Workflow

- **OpenSpec in Claude Code**: invoke skills via `/openspec-propose`, `/openspec-explore`, `/openspec-apply-change`, `/openspec-archive-change`.
- **OpenSpec in Codex**: use `/skills` and select `openspec-propose`, `openspec-explore`, `openspec-apply-change`, `openspec-archive-change`, or invoke them directly as `$openspec-propose`, `$openspec-explore`, `$openspec-apply-change`, `$openspec-archive-change`.
- **OpenSpec in OpenCode**: use `/opsx:propose`, `/opsx:explore`, `/opsx:apply`, `/opsx:archive`.
- **Design**: use `openspec-propose` to draft before implementation. State whether the change touches Tier 1, Tier 2, or an optional extension. Include non-goals, operational impact, risk, and rollback or degradation strategy.
- **Implementation**: use `openspec-apply-change` to implement tasks in order. Do not schedule repo-writing tasks before the relevant spec, plan, and task artifacts are complete.
- **Archive**: use `openspec-archive-change` only after implementation, tests, review, and any required parity follow-ups are complete.

## Verification

- For OpenSpec artifact changes, validate that proposal, specs, design, and tasks satisfy the rules in `openspec/config.yaml` (Tier 1 preserved, Tier 2 degradations explicit, workflow invariants intact, observability and rollback included for security or operations scope).
- For backend changes, install and synchronize Python dependencies with `uv`, then run the relevant backend verification via `uv run`; at minimum use `uv run --project backend ruff check backend/src backend/tests` and `uv run --project backend pytest`, then confirm graph paths still traverse test, diff guard, review, and pre-PR sync before PR creation.
- For frontend changes, confirm the accessibility non-negotiable subset: no color-only state, keyboard reachability of every interactive element, `prefers-reduced-motion` support, and AA text contrast.
- For Helm, Kustomize, RBAC, network policy, or gVisor changes, include manual verification notes and dry-run or shadow-mode output; flag as high-risk.
- For schema changes, verify expand/contract migration discipline with reversibility tests.
- For tenant-boundary, secret-handling, or webhook changes, include observability, audit, and failure-mode notes directly in the PR description.
- UI changes should include screenshots or a short note describing what was manually verified.

## References

- Constitution for SDD artifacts: `openspec/config.yaml`
- Claude Code bootstrap: `CLAUDE.md`
- OpenSpec artifacts (proposals, specs, design, tasks): `openspec/`
