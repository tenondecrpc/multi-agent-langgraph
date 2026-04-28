## Why

Operators and reviewers currently have no way to walk through the LangGraph ticket pipeline visually before a real Jira ticket is in flight. The existing Graph Editor only renders structure and validates JSON; it does not animate transitions, surface per-node agent feedback, or let a human pace the flow for demos, onboarding, or shadow-mode review. A purely client-side, read-only simulator closes that gap without touching repo-write paths, runtime checkpoints, or backend graph activation.

## What Changes

- Add a new "Flow Simulator" tab in the frontend (Vite + React + TypeScript) gated to `admin` and `super-admin` roles.
- Drive the simulation from the same `GraphCandidate` model already used by the Graph Editor; the simulator MUST read the active graph candidate and MUST NOT mutate it.
- Step through nodes in topological order along success edges, with explicit textual feedback per step: current node ID and label, transition reason, simulated agent output, and protected-flag indicator.
- Provide playback controls: Start, Pause, Resume, Step Forward, Reset.
- Provide a "Slow mode" toggle that inserts a fixed 1-second delay between steps for better visualization; default is fast (no delay) to keep tests deterministic.
- Surface a step log (reverse-chronological list) and a current-node highlight on a simple node strip; both update in lockstep.
- Enforce the protected workflow invariants in the simulator UI: the simulation refuses to advance past `coder` if `readiness_gate` has not been visited, and refuses to reach `pr_creator` without traversing `tester`, `reviewer`, and `pre_pr_sync`.
- Honor the accessibility non-negotiable subset: no color-only state (every status has a text label), keyboard reachable controls (Start/Pause/Step/Reset), `prefers-reduced-motion` and the existing in-app `reduced-motion` toggle disable the slow-mode delay automatically, and AA text contrast is preserved.
- Add an aria-live announcement for each step so screen readers receive the same per-step feedback sighted users see.
- Add Vitest coverage for: role gating, step ordering against the active graph, protected-invariant enforcement, slow-mode delay behavior under fake timers, and reduced-motion bypass.

This change is **purely frontend** and read-only. No backend endpoints, no runtime graph activation, no repo writes, and no break-glass pathways are added or modified.

## Capabilities

### New Capabilities
- `frontend-graph-flow-simulator`: in-browser, read-only, role-gated visual simulator for the LangGraph ticket pipeline with stepwise agent feedback, optional 1-second slow-mode delay, protected-invariant enforcement on the simulated success path, and accessibility non-negotiables.

### Modified Capabilities
- (none) The existing `visual-graph-editor`, `admin-and-monitoring-ui`, and `frontend-accessibility-and-localization` specs are not amended; the simulator is additive and lives behind a new tab.

## Impact

- **Tier classification**: Optional extension. Does not weaken any Tier 1 non-negotiable. The simulator is read-only and cannot reach repo-write, runtime graph activation, webhooks, or break-glass paths.
- **Affected code**: `frontend/src/App.tsx` (new tab + role gating), new module `frontend/src/lib/graphSimulator.ts` (pure stepper logic), new component(s) under `frontend/src/components/` (Simulator UI), `frontend/src/i18n/messages.ts` (new keys, English-only), `frontend/src/styles.css` (simulator styles respecting reduced-motion), `frontend/src/App.test.tsx` and a new `graphSimulator.test.ts`.
- **No backend impact**: no new API contracts, no PostgreSQL schema changes, no Redis keys, no observability scope changes. Simulator events stay in browser memory and are cleared on Reset or tab change.
- **Deployment profiles**: identical behavior in `connected` and `air_gapped` profiles since the simulator is fully client-side and uses no network calls.
- **Risk**: low. UI-only, role-gated, read-only, no persistence.
- **Rollback**: revert the frontend change; no migrations, no flags, no data to clean up.
- **Non-goals**: does not execute real LLM calls, does not call the backend `/api/v1/runtime/simulate` (deprecated) or any successor endpoint, does not edit the active or candidate graph, does not replace shadow-mode validation, does not introduce sprite uploads or new locales.
