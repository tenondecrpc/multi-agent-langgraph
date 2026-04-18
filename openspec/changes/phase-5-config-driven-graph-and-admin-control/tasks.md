## 1. Finalize Config Control-Plane Scope

- [ ] 1.1 Confirm that graph config, agent config, shadow mode, versioning, activation, and rollback responsibilities are fully covered by this phase.
- [ ] 1.2 Confirm that all protected workflow invariants from phase 1 remain preserved by the graph configuration contract.
- [ ] 1.3 Cross-check the control-plane requirements against `openspec/config.yaml` to ensure PostgreSQL-backed config and shadow-mode validation remain mandatory.

## 2. Prepare Graph And Agent Config Interfaces

- [ ] 2.1 Define the future graph config schema, handler registry, route validation, and invariant-check interface.
- [ ] 2.2 Define the future agent config schema, role whitelist validation, and test-agent or dry-run interface.
- [ ] 2.3 Define the future activation workflow that compiles, validates, audits, and snapshots configs before worker rollout.

## 3. Prepare Shadow And Rollback Interfaces

- [ ] 3.1 Define the future shadow-run queue, credential, and worker-isolation contracts used before activation.
- [ ] 3.2 Define the future candidate-versus-active comparison report and activation gating logic.
- [ ] 3.3 Define the future rollback and snapshot-retention behavior for in-flight and paused runs.

## 4. Verification Readiness

- [ ] 4.1 Define validation fixtures that prove invalid graphs are rejected even if they compile technically.
- [ ] 4.2 Define shadow-mode validation fixtures that prove read-only isolation and comparison reporting behave as specified.
- [ ] 4.3 Define rollback validation that proves new configs affect only new runs and that pinned snapshots remain available to non-terminal runs.
