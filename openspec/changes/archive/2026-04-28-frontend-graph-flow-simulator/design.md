## Context

The current frontend (`frontend/src/App.tsx`) ships a `Graph Editor` tab that renders the active `GraphCandidate` as JSON and validates protected invariants client-side via `frontend/src/lib/graphValidation.ts`. There is no animated walk-through of the pipeline. Operators that want to demo or onboard teammates currently have to read the JSON, mentally trace edges, and explain the role of each node out loud. The Dashboard does animate one run via a 3500 ms `setInterval` that cycles a single `RunStatus`, but that is not a graph traversal: it does not walk nodes, does not respect protected invariants visibly, and does not surface per-step agent feedback.

Constraints that govern this work:

- Frontend-only, fully client-side. No backend route, no PostgreSQL state, no Redis pub/sub.
- Read-only relative to the active graph candidate. The simulator MUST NOT mutate the graph, the runtime config, or any persisted state.
- Role-gated to `admin` and `super-admin` (mirrors how `graph-editor` and `admin` tabs are gated in `App.tsx:43-48`).
- Accessibility non-negotiable subset: no color-only state, keyboard reachability of every control, `prefers-reduced-motion` plus the existing in-app `reduced-motion` toggle, AA text contrast.
- ASCII-only punctuation; English-only locale with extraction-ready i18n keys.
- Air-gapped parity: identical behavior in `connected` and `air_gapped` profiles because no network calls are made.

## Goals / Non-Goals

**Goals:**
- Provide an in-browser, role-gated `Flow Simulator` tab that walks the active graph candidate node-by-node along success edges from `START` to `pr_creator`.
- Surface per-step textual feedback: current node ID and label, transition reason ("success" by default), simulated agent narration, and a protected-flag indicator.
- Provide playback controls (Start, Pause, Resume, Step, Reset) that are keyboard reachable and have visible focus.
- Provide an opt-in "Slow mode (1s delay)" toggle that paces the simulation. Slow mode is automatically disabled when reduced motion is requested.
- Enforce the protected workflow invariants in the simulator: refuse to advance into `coder` before `readiness_gate` and refuse to reach `pr_creator` without `tester`, `reviewer`, and `pre_pr_sync`. If the active graph violates an invariant, the simulator stops with an explicit, actionable error rather than producing a misleading animation.
- Make the stepper logic a pure module (`frontend/src/lib/graphSimulator.ts`) that is unit-testable without React.
- Cover behavior with Vitest: role gating, step ordering, invariant enforcement, slow-mode delay (using fake timers), and reduced-motion bypass.

**Non-Goals:**
- Calling any backend simulation endpoint. The deprecated `POST /api/v1/runtime/simulate` and any successor (`/api/v2/runtime/simulations`) are explicitly out of scope.
- Editing nodes, edges, routes, interrupts, or activating any candidate snapshot.
- Animating real LLM token streams or real agent outputs. Narration is canned, deterministic strings keyed off node ID.
- Replacing or amending shadow-mode validation. The simulator is a UX aid, not a policy gate.
- Adding new locales, new sprite uploads, or new persistence.
- Introducing pixel-art animation cycles beyond a single highlighted node. Reduced motion is honored by default.

## Decisions

### D1: Pure stepper module separate from React state

`frontend/src/lib/graphSimulator.ts` exposes:

- `buildSimulationPlan(candidate: GraphCandidate): SimulationPlan` - returns an ordered list of `SimulationStep` records derived from success edges starting at `START`, plus a `protectedInvariantErrors: string[]` array.
- `SimulationStep` shape: `{ index, nodeId, label, isProtected, writesRepo, transitionReason, narration }`.
- `simulateAgentNarration(nodeId): string` - canned, deterministic English narration keyed by node ID; used by both runtime stepping and tests.

Rationale: keeping traversal pure makes invariant enforcement and step ordering testable under Vitest without DOM. The React component reduces to "advance an index, render the current step, append to log."

Alternatives considered:
- Drive everything inside the React component using inline reducers: rejected because invariant enforcement deserves direct unit tests and would couple test fixtures to render output.
- Reuse `validateGraphCandidate`: rejected for the traversal step because that helper validates structure, not traversal order. We will, however, call `validateGraphCandidate` first to short-circuit on structural failures and reuse its error strings.

### D2: Slow mode is a single fixed 1000 ms delay, opt-in

The toggle is OFF by default. When ON, the React component schedules each step via `window.setTimeout(advance, 1000)`. When the existing `reduced-motion` toggle or `prefers-reduced-motion: reduce` is active, slow mode is forced OFF and the simulation falls back to manual Step or instant Run.

Rationale: a single, well-known cadence is enough for demos and onboarding without inventing a new speed-control surface. Reduced-motion override is required by the accessibility non-negotiable subset.

Alternatives considered:
- Variable speed slider (0.5x, 1x, 2x): rejected as scope creep for v1 and harder to test deterministically.
- CSS transition-driven pacing: rejected because reduced-motion is supposed to disable transitions, which would break pacing.

### D3: Protected-invariant enforcement reuses the existing required-protected-node list

Reuse the `requiredProtectedNodes` set from `graphValidation.ts`. Additionally enforce traversal-order rules:

- `coder` MUST appear after `readiness_gate` in the planned order.
- `pr_creator` MUST be preceded by `tester`, `reviewer`, and `pre_pr_sync` in the planned order.
- If either rule is violated, `buildSimulationPlan` returns an empty `steps` array and populates `protectedInvariantErrors` with explicit messages. The UI then displays an error panel and disables Start.

Rationale: aligns with the workflow invariants in `openspec/config.yaml` and the existing graph editor's validation contract. Keeping enforcement on the simulator side prevents producing a misleading animation when the active candidate is invalid.

### D4: Role gating mirrors existing tabs

Add `flow-simulator` to `TabKey` and to the `roleTabs` map for `admin` and `super-admin` only. Lower roles cannot navigate to it via the side nav, and the tab body returns null if `role` is below `admin`. This mirrors `graph-editor` and `admin` gating in `App.tsx:43-48`.

### D5: No network, no persistence, no audit hook

The simulator does not call `fetch`, does not write to `localStorage`, does not emit OpenTelemetry spans, and does not modify the live status stream announcer. The aria-live announcement region is a separate node scoped to the simulator panel; it does not collide with the existing top-level live region used by the Dashboard.

Rationale: keeps blast radius zero. There is no tenant boundary to cross because the simulator never leaves the browser. Air-gapped parity is automatic.

### D6: Accessibility approach

- Every status pill in the simulator carries a text label, mirroring the `Runtime states include text labels and not just color` legend already in the Dashboard.
- The current-node indicator uses both a CSS state class and a visible text label (e.g., `Current step: coder (Coder)`).
- Buttons (`Start`, `Pause`, `Resume`, `Step`, `Reset`) are real `<button>` elements with `type="button"` and visible labels. Focus is managed so that after Reset, focus returns to Start.
- The slow-mode checkbox is a labeled `<input type="checkbox">`.
- The step log is an ordered list with `role="log"` and `aria-live="polite"`. Each new step appends a list item containing the same text the sighted user sees.
- Honors the existing `reduced-motion` toggle by disabling slow-mode delay and any CSS transitions on the node strip.

### D7: i18n keys, English-only

Add new keys under `frontend/src/i18n/messages.ts` (English only at GA, per the Tier 2 i18n degradation): `flowSimulator`, `flowSimulatorIntro`, `slowModeLabel`, `simulatorStart`, `simulatorPause`, `simulatorResume`, `simulatorStep`, `simulatorReset`, `simulatorLogHeading`, `simulatorInvariantBlocked`, `simulatorReducedMotionNotice`, narration keys for each protected node ID. Extraction-ready structure preserved.

## Risks / Trade-offs

- [Risk] Operators mistake the simulator for real execution and assume PRs were created. → Mitigation: persistent banner reading "Simulation only. No code, tests, or PRs are produced." plus a footer note that links to the runtime status stream. Buttons never use real-execution verbs like "Run ticket".
- [Risk] Active candidate is structurally invalid or violates protected invariants. → Mitigation: `buildSimulationPlan` returns errors and the UI shows an explicit blocking message; Start is disabled.
- [Risk] Slow-mode timers leak across tab changes. → Mitigation: clear timers in `useEffect` cleanup when the tab unmounts and on Reset.
- [Risk] Accessibility regression by adding animated highlight. → Mitigation: highlight uses CSS class only; reduced-motion globally suppresses transitions via existing `.reduced-motion *` rule. No animations are introduced beyond the existing global rule.
- [Risk] Test flakiness due to real timers. → Mitigation: Vitest fake timers (`vi.useFakeTimers()`) for slow-mode tests; instant mode for default tests.
- [Risk] Future divergence from the active graph contract. → Mitigation: simulator imports `GraphCandidate` and the protected-node list from existing modules instead of redefining them.

## Migration Plan

- No data migration. UI-only.
- Deploy: ship the frontend build along with the backend release; no Helm, no schema, no flag rollouts required.
- Rollback: revert the frontend commit. Tab disappears; no residual state because nothing was persisted.

## Open Questions

- (none blocking) Future enhancement could let an operator paste an arbitrary `GraphCandidate` JSON to simulate a candidate snapshot. That is deferred and would be additive without changing the contract above.
