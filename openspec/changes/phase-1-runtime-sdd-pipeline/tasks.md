## 1. Finalize Runtime SDD Contracts

- [ ] 1.1 Confirm that the artifact lifecycle, repo-write gate, retry routing, and escalation reasons in this phase fully cover the runtime flow described in `docs/PLAN.md`.
- [ ] 1.2 Review every requirement against `openspec/config.yaml` and `AGENTS.md` to ensure Tier 1 invariants and Tier 2 degradation rules remain unchanged.
- [ ] 1.3 Cross-reference later OpenSpec phases so platform, security, UI, and operations specs extend this runtime contract instead of redefining it.

## 2. Prepare Planner and State Interfaces

- [ ] 2.1 Define the future backend interfaces for planner-owned artifacts, including constitution loading, feature spec generation, clarification notes, implementation plans, and task lists.
- [ ] 2.2 Define the future persisted ticket state model, including run identity, config snapshot pinning, checkpoint fields, and resume metadata.
- [ ] 2.3 Define the future storage contract for checkpoint state versus long-term memory versus config snapshots, with tenant-scoped namespaces and audit expectations.

## 3. Plan Guarded Flow Implementation

- [ ] 3.1 Plan the future graph nodes and routing functions that enforce the protected success path, retry limits, diff size guard, merge conflict guard, and escalation sink registration.
- [ ] 3.2 Plan the future context resolution implementation so local and first-party sources are exhausted before external research is attempted.
- [ ] 3.3 Plan the future degradation toggle for single-pass clarification so GA can ship without weakening the autonomous-first default.

## 4. Verification Readiness

- [ ] 4.1 Define validation fixtures that prove repo-writing cannot begin before `spec_ready_for_implementation` is true and a task list exists.
- [ ] 4.2 Define validation fixtures for resume behavior that prove paused and retried runs keep the same `run_id`, `thread_id`, and config snapshot.
- [ ] 4.3 Define validation fixtures that prove every failure terminal path maps to a registered escalation reason and sink.
- [ ] 4.4 Define validation fixtures that prove the PR creator refuses to open a pull request when required unit or end-to-end tests declared in the task list are missing, skipped, or failing.
- [ ] 4.5 Define validation fixtures that prove reviewer approval is blocked while linting, type or static analysis, or declared SOLID-aligned design checks fail on the agent-produced diff.
