## 1. Finalize Runtime SDD Contracts

- [x] 1.1 Confirm that the artifact lifecycle, repo-write gate, retry routing, and escalation reasons in this phase fully cover the runtime flow described in `docs/PLAN.md`.
- [x] 1.2 Review every requirement against `openspec/config.yaml` and `AGENTS.md` to ensure Tier 1 invariants and Tier 2 degradation rules remain unchanged.
- [x] 1.3 Cross-reference later OpenSpec phases so platform, security, UI, and operations specs extend this runtime contract instead of redefining it.

## 2. Prepare Planner and State Interfaces

- [x] 2.1 Define the future backend interfaces for planner-owned artifacts, including constitution loading, feature spec generation, clarification notes, implementation plans, and task lists.
- [x] 2.2 Define the future persisted ticket state model, including run identity, config snapshot pinning, checkpoint fields, and resume metadata.
- [x] 2.3 Define the future storage contract for checkpoint state versus long-term memory versus config snapshots, with tenant-scoped namespaces and audit expectations.

## 3. Plan Guarded Flow Implementation

- [x] 3.1 Plan the future graph nodes and routing functions that enforce the protected success path, retry limits, diff size guard, merge conflict guard, and escalation sink registration.
- [x] 3.2 Plan the future context resolution implementation so local and first-party sources are exhausted before external research is attempted.
- [x] 3.3 Plan the future degradation toggle for single-pass clarification so GA can ship without weakening the autonomous-first default.

## 4. Verification Readiness

- [x] 4.1 Define validation fixtures that prove repo-writing cannot begin before `spec_ready_for_implementation` is true and a task list exists.
- [x] 4.2 Define validation fixtures for resume behavior that prove paused and retried runs keep the same `run_id`, `thread_id`, and config snapshot.
- [x] 4.3 Define validation fixtures that prove every failure terminal path maps to a registered escalation reason and sink.
- [x] 4.4 Define validation fixtures that prove the PR creator refuses to open a pull request when required unit or end-to-end tests declared in the task list are missing, skipped, or failing.
- [x] 4.5 Define validation fixtures that prove reviewer approval is blocked while linting, type or static analysis, or declared SOLID-aligned design checks fail on the agent-produced diff.

## 5. Implement Phase 1 Runtime Backbone

- [x] 5.1 Scaffold the Python backend under `backend/` with `uv`, add the phase-1 runtime dependencies, and document the new sync, lint, and test commands.
- [x] 5.2 Implement executable runtime models for planner-owned artifacts, task-list readiness, ticket execution identity, context provenance, and in-memory checkpoint persistence.
- [x] 5.3 Implement the guarded phase-1 workflow in code, including repo-write gating, clarification routing, bounded test and review retries, pre-PR guards, and escalation sink validation.
- [x] 5.4 Add API and package scaffolding plus automated tests for repo-write gating, retry and escalation behavior, context ordering, and identity-preserving pause and resume flows.
- [x] 5.5 Run `uv`-based lint and test verification for the backend slice and keep phase 1 unarchived unless the implementation checks pass.
