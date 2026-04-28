## ADDED Requirements

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
