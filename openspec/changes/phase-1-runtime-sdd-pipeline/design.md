## Context

This phase extracts the product's runtime SDD backbone from `docs/PLAN.md`. The goal is to make the artifact chain, state contract, context policy, and guarded ticket flow explicit before the repository plans infrastructure, security, or frontend work in deeper slices.

## Goals / Non-Goals

**Goals:**
- Define the planner-owned artifact lifecycle as the only legal starting point for repo-writing behavior.
- Pin the execution identity, config snapshot rules, and checkpoint compatibility rules used across retries and resumes.
- Define the context resolution order so later phases do not invent competing lookup or research paths.
- Encode the protected success path and failure routing rules that every activatable workflow must preserve.

**Non-Goals:**
- Kubernetes topology, Helm structure, and sandbox hardening details.
- Authentication, RBAC, credential storage, and webhook security controls.
- LLM routing, budget reservations, metering, billing, and provider failover.
- Frontend, graph editor, and observability implementation details.

## Decisions

- The runtime artifact chain is modeled as a first-class product capability, not an implementation detail of the planner prompt.
- Repo-writing is guarded by two explicit state conditions: `spec_ready_for_implementation=true` and the presence of a task list.
- Clarification remains autonomous-first. Human approval is allowed only on registered exception paths after ambiguity cannot be resolved within configured bounds.
- Execution identity is split between the business identity (`ticket_key`) and the run identity (`run_id`), with the `thread_id` derived from the run identity so retries and resumes remain deterministic.
- Checkpoint state, long-term memory, and config snapshots remain distinct persisted concerns even when they are stored in the same PostgreSQL control plane.
- Context resolution follows a single local-first order: Jira, repo, run-state and memory, optional internal knowledge, first-party APIs, and external research last.
- The optional internal knowledge path must remain tenant-scoped, read-only during execution, and must reuse PostgreSQL with `pgvector` instead of introducing a new datastore.
- The protected success path always includes planner-owned SDD artifacts, implementation, tests, review, and pre-PR sync before PR creation.

## Risks / Trade-offs

- This phase is intentionally foundational, so weak wording here would leak ambiguity into every later phase.
- Some requirements reference later phases, which creates cross-phase coupling, but that coupling is preferable to allowing each later change to reinterpret the runtime contract.
- The full autonomous clarify loop is a Tier 2 GA target, so this phase must explicitly permit the single-pass degradation path without weakening the Tier 1 repo-write gate or break-glass rules.
