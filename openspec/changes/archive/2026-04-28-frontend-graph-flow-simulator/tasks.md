## 1. i18n And Sample Data

- [x] 1.1 Add new English keys to `frontend/src/i18n/messages.ts`: `flowSimulator`, `flowSimulatorIntro`, `flowSimulatorOnlyNotice`, `slowModeLabel`, `simulatorStart`, `simulatorPause`, `simulatorResume`, `simulatorStep`, `simulatorReset`, `simulatorLogHeading`, `simulatorInvariantBlocked`, `simulatorReducedMotionNotice`, `simulatorIdle`, `simulatorRunning`, `simulatorPaused`, `simulatorCompleted`, and one canned narration key per protected node (`narrationLoadConstitution`, `narrationCreateFeatureSpec`, `narrationClarify`, `narrationCreatePlan`, `narrationCreateTaskList`, `narrationReadinessGate`, `narrationCoder`, `narrationTester`, `narrationReviewer`, `narrationPrePrSync`, `narrationPrCreator`).
- [x] 1.2 Verify the `MessageKey` type derives the new keys at compile time and existing tests still pass.

## 2. Pure Stepper Module

- [x] 2.1 Create `frontend/src/lib/graphSimulator.ts` exporting `SimulationStep`, `SimulationPlan`, `buildSimulationPlan(candidate: GraphCandidate): SimulationPlan`, and `simulateAgentNarration(nodeId: string): string`.
- [x] 2.2 Implement traversal: start at `START`, follow `transition: "success"` edges, build an ordered step array with `{ index, nodeId, label, isProtected, writesRepo, transitionReason, narration }`. Pull narration via `simulateAgentNarration` keyed on node ID. Use the existing `requiredProtectedNodes` set from `frontend/src/lib/graphValidation.ts` (export it from that module if needed) so both modules agree on protected identifiers.
- [x] 2.3 Enforce traversal-order invariants: `coder` after `readiness_gate`; `pr_creator` after `tester`, `reviewer`, and `pre_pr_sync`. On violation, return `{ steps: [], protectedInvariantErrors: [<explicit messages>] }`.
- [x] 2.4 Reuse `validateGraphCandidate` to short-circuit on structural failures and surface its errors through `protectedInvariantErrors`.
- [x] 2.5 Add `frontend/src/lib/graphSimulator.test.ts` covering: valid plan length and order against `activeGraphCandidate`, invariant violation against `invalidGraphCandidate`, structural-failure short-circuit, and stable narration per node ID.

## 3. Simulator UI Component

- [x] 3.1 Create `frontend/src/components/FlowSimulator.tsx` accepting props `{ candidate: GraphCandidate; reducedMotion: boolean }` and rendering: a persistent simulation-only notice, a current-step area, a node strip with a current-node highlight that has both a CSS state and a text label, the Slow mode checkbox, the controls row (`Start`, `Pause`, `Resume`, `Step`, `Reset`), the step log (`role="log"`, `aria-live="polite"`), and an inline error region for invariant blocks.
- [x] 3.2 Implement the React state machine: `idle | running | paused | blocked | completed`. On Start with Slow mode ON and `reducedMotion === false`, schedule `setTimeout(advance, 1000)` per step; otherwise rely on Step. Always clear pending timers on Pause, Reset, unmount, and when `reducedMotion` flips to true.
- [x] 3.3 Disable Start, Step, and Resume when the plan is blocked by invariants; render the explicit error list using `protectedInvariantErrors`.
- [x] 3.4 Add focus management: after Reset, move focus back to Start. Ensure each control is a real `<button type="button">` with a visible label and visible focus ring (reuse existing `:focus-visible` styles).
- [x] 3.5 Honor reduced motion: when the user has reduced motion (`reducedMotion === true`) and Slow mode is checked, render a textual notice explaining automatic pacing is disabled and that Step must be used.
- [x] 3.6 Add `frontend/src/styles.css` rules under a `.flow-simulator` scope for the node strip, current-node highlight, log, and controls. Do not introduce animations beyond what the existing `.reduced-motion *` global rule already disables. Maintain AA contrast.

## 4. App Integration

- [x] 4.1 In `frontend/src/App.tsx`, add `flow-simulator` to `TabKey` and to the `roleTabs` map for `admin` and `super-admin` only. Add the label to `liveTabLabels`.
- [x] 4.2 Render `<FlowSimulator candidate={activeGraphCandidate} reducedMotion={reducedMotion} />` when `tab === "flow-simulator"` and the role is `admin` or higher; otherwise render nothing for that tab.
- [x] 4.3 Confirm the existing top-level live announcement is not duplicated; the simulator owns its own scoped live region inside the panel.

## 5. Tests

- [x] 5.1 Extend `frontend/src/App.test.tsx` with: role gating (viewer cannot see `Flow Simulator`, admin can), invariant-block messaging with a forced invalid candidate, slow-mode pacing under `vi.useFakeTimers()` advancing in 1000 ms increments, reduced-motion override forcing manual stepping, and assertion that `globalThis.fetch` is not called by simulator interactions.
- [x] 5.2 Add a focused unit suite in `frontend/src/lib/graphSimulator.test.ts` for plan building, ordering, and narration determinism.

## 6. Verification

- [x] 6.1 Run `npm install --prefix frontend` then `npm run --prefix frontend test -- --run` from the repository root and confirm the suite is green.
- [x] 6.2 Run `npm run --prefix frontend build` from the repository root and confirm the production build succeeds with no new warnings on the touched files.
- [x] 6.3 Manually verify in a dev server that: every simulator control is keyboard reachable with a visible focus ring, each status carries a text label and not just color, AA contrast holds for the new copy, and toggling the in-app `Reduced motion` switch suppresses 1-second auto-advance.
- [x] 6.4 Capture a short note (and optionally a screenshot) for the PR description listing what was manually verified, per the repo `Verification` checklist for UI changes.

## 7. Documentation And Archive

- [x] 7.1 Update operator documentation under `docs/` only if an operator-facing description is required; otherwise note in the PR description that the simulator is self-explanatory and ephemeral.
- [x] 7.2 After implementation, tests, and verification are complete, run `openspec-archive-change` to archive `frontend-graph-flow-simulator`.
