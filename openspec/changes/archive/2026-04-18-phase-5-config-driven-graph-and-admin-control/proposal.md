## Why

`docs/PLAN.md` makes the runtime graph and agent configuration explicitly config-driven, versioned, auditable, and shadow-validated before activation. Those control-plane behaviors need their own OpenSpec phase so later implementation does not hard-code topology or bypass protected workflow invariants.

## What Changes

- Define the graph configuration model, compile-time validation rules, and protected workflow invariants for activatable configs.
- Define shadow-mode behavior, including read-only credentials, separate queueing, isolated worker identity, and comparison reporting before activation.
- Define agent configuration governance, including role-scoped tool whitelists, model settings, retry limits, and dry-run testing surfaces.
- Define config versioning, auditability, activation rules, rollback, and in-flight snapshot pinning behavior.
- Add a contract-level backend control-plane slice that implements graph validation, agent-config validation, shadow comparison, and versioned snapshot activation without introducing the full PostgreSQL or admin API surfaces yet.
- Classify this phase as Tier 1 for config storage, shadow validation, rollback, and invariant preservation, with the Tier 2 graph-editor degradation path preserved for later UI work.

## Capabilities

### New Capabilities
- `graph-configuration-runtime`: Graph config schema, compile and validate rules, protected workflow invariants, and activation preconditions.
- `graph-shadow-mode`: Read-only replay environment, candidate-versus-active comparison, and activation gating.
- `agent-configuration-governance`: Role-scoped agent config, backend validation, dry-run testing, and least-privilege enforcement.
- `config-versioning-and-rollback`: Versioned PostgreSQL config storage, audit trail, activation rules, rollback, and snapshot retention for active runs.

### Modified Capabilities
- None.

## Impact

- Future configuration schema and validation code in `backend/`.
- Admin APIs and activation workflows.
- Worker startup behavior and config snapshot loading.
- Later UI work for graph editing, agent config forms, and dry-run testing.
- Backend verification now includes control-plane tests for invariant rejection, role-bound dry runs, shadow activation gating, and rollback-safe snapshot retention.
