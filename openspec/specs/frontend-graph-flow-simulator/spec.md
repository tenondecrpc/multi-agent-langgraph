# frontend-graph-flow-simulator Specification

## Purpose

Define the browser-only Flow Simulator experience for safely teaching and validating the protected ticket-to-PR workflow before any real ticket execution occurs.

## Requirements

### Requirement: Flow Simulator Tab Is Role-Gated

The frontend SHALL expose a "Flow Simulator" tab that is reachable only by operators whose role is `admin` or `super-admin`. Lower-privilege roles (`viewer`, `operator`) MUST NOT see the tab in the navigation panel and MUST NOT be able to render its content even if the tab key is forced via state manipulation in the same session.

#### Scenario: Viewer cannot see the simulator tab
- **WHEN** an operator with role `viewer` opens the application
- **THEN** the navigation panel does not list "Flow Simulator"
- **AND** no simulator content is rendered

#### Scenario: Admin sees the simulator tab
- **WHEN** an operator with role `admin` switches roles to `admin`
- **THEN** the navigation panel lists "Flow Simulator"
- **AND** clicking it opens the simulator content area

### Requirement: Simulator Is Read-Only And Browser-Only

The Flow Simulator SHALL run entirely in the browser and SHALL NOT call any backend simulation, runtime, repo-write, or graph-activation endpoint. The simulator MUST NOT modify the active or candidate graph snapshot. The simulator MUST behave identically in `connected` and `air_gapped` deployment profiles.

#### Scenario: Running a simulation does not call the backend
- **WHEN** an admin starts, steps, pauses, resumes, or resets the simulator
- **THEN** no `fetch` request is issued by the simulator code path
- **AND** no graph snapshot is mutated client-side or server-side

#### Scenario: Air-gapped parity
- **WHEN** the deployment profile is `air_gapped`
- **THEN** the Flow Simulator behaves identically to the `connected` profile
- **AND** no air-gap-specific code path is required

### Requirement: Stepwise Agent Feedback Is Surfaced In Text

For each simulated step the Flow Simulator MUST surface, in user-visible text, at minimum: the current node ID, the human-readable node label, the transition reason taken to enter the node, and a deterministic agent narration describing what the agent simulates doing at that node. Each step MUST also indicate whether the node is a protected workflow node.

#### Scenario: Per-step feedback is rendered
- **WHEN** the simulator advances to the `coder` node
- **THEN** the current-step area shows the node ID `coder`, the label `Coder`, the transition reason `success`, and the canned narration for `coder`
- **AND** the protected-flag indicator is shown with a text label and not a color alone

### Requirement: Optional 1-Second Slow Mode

The Flow Simulator SHALL provide a "Slow mode" toggle that, when ON and Start has been pressed, paces automatic step advancement at one step per 5000 ms. The toggle SHALL default to OFF. When the user has reduced motion preferences active through the in-app `reduced-motion` toggle, Slow mode SHALL be ignored and automatic stepping SHALL fall back to the user-driven Step button.

#### Scenario: Slow mode paces automatic advancement
- **WHEN** an admin enables Slow mode and presses Start
- **THEN** the simulator advances one step every 5000 ms

#### Scenario: Reduced motion overrides slow mode
- **WHEN** the in-app reduced-motion toggle is on and Slow mode is enabled
- **THEN** automatic advancement does not run on a 5000 ms cadence
- **AND** a textual notice explains that automatic pacing is disabled and that the Step button must be used

### Requirement: Simulator Renders Visual Agent Feedback

The Flow Simulator SHALL render a visual agent stage for every valid simulation step. The stage MUST show the active agent role, a bundled sprite-sheet frame for that role, the current node ID, the node label, the transition reason, whether the node is protected, and deterministic narration describing what the agent is doing.

The visual stage MUST remain supplemental to text feedback. The same step information MUST remain available in the current-step area and `aria-live` log.

#### Scenario: Active coder feedback is visible and textual

- **WHEN** the simulator advances to the `coder` node
- **THEN** the visual stage shows the coder sprite and role label
- **AND** the visible text includes `coder`, `Coder`, `success`, the protected-node state, and the coder narration
- **AND** the live log contains the same deterministic narration

#### Scenario: Unknown nodes keep a safe fallback

- **WHEN** a valid custom graph contains a node without a role-specific sprite mapping
- **THEN** the simulator renders a default planner-style sprite
- **AND** the visible text still includes the node ID, node label, transition reason, protected-node state, and fallback narration

### Requirement: Simulator Renders A Dynamic Multi-Agent Office

The Flow Simulator SHALL render a pixel-art office scene where planner, reviewer, coder, tester, and PR creator are visible together for every valid simulation step. The scene MUST derive active agents, movement positions, facing direction, speech, and handoff state from the current simulation step.

#### Scenario: All agents are visible in the office

- **WHEN** the simulator has advanced to any valid step
- **THEN** the office scene shows planner, reviewer, coder, tester, and PR creator agents
- **AND** each agent has a text role label available in the DOM

#### Scenario: Review interaction moves agents together

- **WHEN** the simulator advances to a review-oriented step
- **THEN** the active agents are positioned as an interaction pair rather than isolated at their home desks
- **AND** the scene exposes text describing the interaction phase

### Requirement: Dynamic Office Preserves Accessible Feedback

The dynamic office SHALL be supplemental to existing simulator text feedback. The current step facts and live log MUST still include node ID, label, transition reason, protection state, repository write state, and deterministic narration.

#### Scenario: Screen-reader feedback remains complete

- **WHEN** the simulator advances to `tester`
- **THEN** the live log includes the tester node ID, label, transition reason, protection state, and narration
- **AND** the office scene includes a visible tester speech bubble or equivalent text

### Requirement: Dynamic Office Honors Reduced Motion

When reduced motion is enabled, the dynamic office SHALL show the current office positions and speech without walking animation, sprite-frame animation, or automatic slow-mode advancement.

#### Scenario: Reduced motion keeps state visible

- **WHEN** reduced motion is enabled and the simulator advances manually
- **THEN** all agents remain visible in their current step positions
- **AND** movement animation is disabled while text feedback remains visible

### Requirement: Simulator Enforces Protected Workflow Invariants

The Flow Simulator MUST refuse to produce a simulated path that violates the protected workflow invariants. Specifically: `coder` MUST NOT appear before `readiness_gate`, and `pr_creator` MUST be preceded by `tester`, `reviewer`, and `pre_pr_sync`. If the active graph candidate violates either rule, the simulator SHALL display an explicit blocking error and SHALL disable the Start, Step, and Resume controls until a valid candidate is selected.

#### Scenario: Invalid candidate blocks simulation
- **WHEN** the active candidate is missing `reviewer` and `pre_pr_sync`
- **THEN** the simulator shows an explicit error listing the missing protected nodes
- **AND** Start, Step, and Resume are disabled

#### Scenario: Out-of-order coder is rejected
- **WHEN** the active candidate places `coder` before `readiness_gate`
- **THEN** the simulator shows an error stating that the repo-writing node appears before the readiness gate
- **AND** the simulator does not begin animating

### Requirement: Simulator Controls Are Keyboard Reachable

All simulator controls (Start, Pause, Resume, Step, Reset, and the Slow mode toggle) MUST be keyboard reachable, expose a visible focus indicator, and use real `<button>` and `<input>` elements with text labels.

#### Scenario: Keyboard reaches every control
- **WHEN** an operator tabs through the simulator panel
- **THEN** focus visits each of Start, Pause, Resume, Step, Reset, and the Slow mode checkbox in document order
- **AND** the focus indicator is visible at every stop

### Requirement: Simulator Provides Accessible Live Updates

The Flow Simulator SHALL provide an `aria-live="polite"` log region that mirrors each rendered step in plain text, so that screen reader users receive the same per-step feedback as sighted users. Status indicators in the simulator MUST include text labels and MUST NOT rely on color alone.

#### Scenario: Live region announces steps
- **WHEN** the simulator advances to a new node
- **THEN** a new entry is appended to the polite live region containing the node ID, label, transition reason, and narration
- **AND** the entry persists in the visible step log

### Requirement: Simulator Is Clearly Labeled As Simulation

The Flow Simulator panel SHALL display a persistent, plain-text notice clarifying that no real Jira ticket is being processed, no LLM tokens are being spent, and no Pull Request is being opened. Control labels SHALL NOT use verbs that imply real execution (no "Run ticket", no "Create PR").

#### Scenario: Persistent simulation-only notice
- **WHEN** an admin opens the Flow Simulator
- **THEN** a non-dismissible notice reads that the panel is a simulation only and produces no real code, tests, or PRs

### Requirement: Simulator State Is Ephemeral

Simulator state (current step, log entries, paused/running flag) MUST live only in component memory for the active session. Switching tabs, refreshing the page, or signing out MUST clear the state. The simulator MUST NOT persist to `localStorage`, `sessionStorage`, IndexedDB, or any backend store.

#### Scenario: Tab switch clears simulator state
- **WHEN** an admin runs a partial simulation, switches to another tab, and returns to Flow Simulator
- **THEN** the simulator is reset and the step log is empty

#### Scenario: No persistence APIs are touched
- **WHEN** the simulator runs to completion
- **THEN** no key is added to `localStorage`, `sessionStorage`, or IndexedDB
- **AND** no network request is issued
