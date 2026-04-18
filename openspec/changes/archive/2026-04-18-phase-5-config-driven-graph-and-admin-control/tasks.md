## 1. Finalize Config Control-Plane Scope

- [x] 1.1 Confirm that graph config, agent config, shadow mode, versioning, activation, and rollback responsibilities are fully covered by this phase.
- [x] 1.2 Confirm that all protected workflow invariants from phase 1 remain preserved by the graph configuration contract.
- [x] 1.3 Cross-check the control-plane requirements against `openspec/config.yaml` to ensure PostgreSQL-backed config and shadow-mode validation remain mandatory.

## 2. Prepare Graph And Agent Config Interfaces

- [x] 2.1 Define the future graph config schema, handler registry, route validation, and invariant-check interface.
- [x] 2.2 Define the future agent config schema, role whitelist validation, and test-agent or dry-run interface.
- [x] 2.3 Define the future activation workflow that compiles, validates, audits, and snapshots configs before worker rollout.

## 3. Prepare Shadow And Rollback Interfaces

- [x] 3.1 Define the future shadow-run queue, credential, and worker-isolation contracts used before activation.
- [x] 3.2 Define the future candidate-versus-active comparison report and activation gating logic.
- [x] 3.3 Define the future rollback and snapshot-retention behavior for in-flight and paused runs.

## 4. Verification Readiness

- [x] 4.1 Define validation fixtures that prove invalid graphs are rejected even if they compile technically.
- [x] 4.2 Define shadow-mode validation fixtures that prove read-only isolation and comparison reporting behave as specified.
- [x] 4.3 Define rollback validation that proves new configs affect only new runs and that pinned snapshots remain available to non-terminal runs.

## 5. Implement Contract-Level Control-Plane Slice

- [x] 5.1 Add backend control-plane modules for graph config compilation, invariant validation, and protected `ticket_to_pr_v1` handler checks.
- [x] 5.2 Add agent-configuration validation and dry-run enforcement that preserves runtime role boundaries and default role-to-model mappings.
- [x] 5.3 Add shadow comparison and versioned snapshot storage primitives that support activation gating, rollback, and pinned-snapshot retention for non-terminal runs.
- [x] 5.4 Verify the backend slice with `uv run --project backend ruff check backend/src backend/tests` and `uv run --project backend pytest` before archiving.
