## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Optional 1-Second Slow Mode

The Flow Simulator SHALL provide a "Slow mode" toggle that, when ON and Start has been pressed, paces automatic step advancement at one step per 5000 ms. The toggle SHALL default to OFF. When the user has reduced motion preferences active through the in-app `reduced-motion` toggle, Slow mode SHALL be ignored and automatic stepping SHALL fall back to the user-driven Step button.

#### Scenario: Slow mode paces automatic advancement

- **WHEN** an admin enables Slow mode and presses Start
- **THEN** the simulator advances one step every 5000 ms

#### Scenario: Reduced motion overrides slow mode

- **WHEN** the in-app reduced-motion toggle is on and Slow mode is enabled
- **THEN** automatic advancement does not run on a 5000 ms cadence
- **AND** a textual notice explains that automatic pacing is disabled and that the Step button must be used
