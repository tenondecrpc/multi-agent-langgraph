## Context

This phase defines the control plane that governs runtime behavior without requiring source-code edits for normal operations. The repository constitution already requires PostgreSQL-backed config, versioning, rollback, and shadow validation, so the graph and agent configuration surfaces need explicit OpenSpec contracts before backend and frontend implementation begin.

## Goals / Non-Goals

**Goals:**
- Define a config-driven graph runtime that still preserves all protected workflow invariants.
- Define a read-only shadow-mode activation path that produces evidence before a new config becomes active.
- Define agent configuration as a validated, least-privilege surface rather than a free-form prompt and tool editor.
- Define versioning, audit, rollback, and snapshot pinning for graph and agent config changes.

**Non-Goals:**
- Kubernetes deployment internals or sandbox hardening details.
- Tenant auth, webhook trust, or provider budgeting details.
- Frontend interaction design for graph editing or dashboard visuals.
- Release rollout, SLO policy, or chaos testing details.

## Decisions

- Runtime topology remains config-driven, but activatable graphs are validated against protected v1 invariants instead of being treated as arbitrary DAGs.
- Graph validation is stronger than simple compile success. A graph that compiles but bypasses required guards is still invalid for activation.
- Shadow mode uses separate credentials, queueing, service identity, and network policy to provide defense in depth rather than relying on a single application-level read-only flag.
- Agent config is modeled as a role-bound operational contract. Admins may tune within role limits, but they may not grant arbitrary tools or bypass least-privilege boundaries.
- Config versions are stored in PostgreSQL with audit trail and rollback. New versions apply only to new runs, while active or paused runs keep their pinned snapshot until completion.
- Dry-run or test-agent surfaces are part of the control-plane contract, but they remain subject to the same model, tool, and validation rules as production config.

## Risks / Trade-offs

- A flexible graph editor without invariant validation would be dangerous, so this phase intentionally prioritizes safety over maximum graph freedom.
- Shadow mode is operationally expensive because it duplicates some runtime infrastructure, but it provides concrete evidence before risky activations.
- Versioned config and snapshot retention add state-management complexity, but they are necessary to keep retries and resumes deterministic across config changes.
