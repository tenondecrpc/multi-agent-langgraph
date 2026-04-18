## Why

`docs/PLAN.md` already defines the desired ticket-to-PR behavior, but it is still a single monolithic plan. The repository needs a first OpenSpec phase that turns the runtime SDD contract into explicit, reviewable capabilities before platform, security, UI, and operations work are planned in detail.

## What Changes

- Define the planner-owned runtime artifact lifecycle that must exist before any repo-writing step is allowed.
- Specify the canonical ticket execution state, including run identity, checkpoint compatibility, and persisted artifact context.
- Specify the local-first context resolution policy, including the optional internal knowledge retrieval path without introducing a new datastore.
- Specify the autonomous ticket execution flow, including retry boundaries, diff and merge guards, escalation reasons, and the break-glass-only interrupt model.
- Keep this phase SDD-only. No application implementation is introduced in this change.
- Classify this phase as Tier 1 for repo-write safety and protected workflow invariants, with the Tier 2 clarify-loop degradation path captured explicitly.

## Capabilities

### New Capabilities
- `runtime-artifact-lifecycle`: Planner-owned artifact generation, repo-write gate, clarify behavior, and break-glass escalation rules.
- `ticket-execution-state`: Canonical state model, pinned config identity, checkpoint persistence, and resume compatibility requirements.
- `context-resolution-policy`: Local-first context order, role boundaries for research, and optional tenant-scoped internal retrieval requirements.
- `autonomous-ticket-flow`: End-to-end execution order, retry routing, diff and merge guards, mandatory review and test traversal, and escalation mapping.

### Modified Capabilities
- None.

## Impact

- Future backend graph compilation and node contracts.
- Planner, reviewer, coder, tester, and PR creator role boundaries.
- PostgreSQL checkpoint, memory, and config snapshot expectations.
- Later platform, security, and UI phases that depend on this runtime contract.
