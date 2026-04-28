# pixel-art-control-room Specification

## Purpose
TBD - created by archiving change phase-6-operator-ui-and-control-room. Update Purpose after archive.
## Requirements
### Requirement: Control Room Is The Primary Monitoring Experience

The monitoring UI MUST provide a pixel-art control room that communicates runtime state at a glance.

#### Scenario: Control room represents active runtime roles and states
- **WHEN** tickets move through planner, coder, tester, reviewer, PR creation, or exception states
- **THEN** the control room maps those states into visible agent or scene representations that communicate progress and status clearly

#### Scenario: Multiple concurrent tickets remain visible
- **WHEN** several tickets are active in parallel
- **THEN** the control room still conveys concurrent activity rather than collapsing the system to a single-ticket metaphor

### Requirement: Visual Direction Follows The Declared Reference

The control room MUST follow the copy-first visual rule described in `docs/PLAN.md`, preserving the intended scene density, rhythm, and motion language unless a documented product reason requires divergence. Bundled agent sprites used by the control room or simulator MUST come from the declared `the-dev-squad` reference sprite sheets unless a later approved SDD change replaces the reference.

#### Scenario: Visual implementation stays faithful
- **WHEN** the control-room design is implemented later
- **THEN** it uses the declared reference as the primary baseline for layout logic, sprite treatment, and animation feel
- **AND** major stylistic divergence requires explicit product rationale

#### Scenario: Simulator and control room share reference sprite treatment

- **WHEN** the Flow Simulator renders agent feedback using bundled sprites
- **THEN** the sprite treatment matches the declared reference agent sheets
- **AND** future control-room parity can reuse the same bundled assets without remapping placeholder art

### Requirement: Office Scene Shows Agent Interactions

Pixel-art office experiences SHALL show agent collaboration as interactions between visible agents, not only as isolated role cards. Review, test, implementation, and PR creation states MUST have distinct visual arrangements that communicate which agents are collaborating.

#### Scenario: Collaboration is visually distinguishable

- **WHEN** the active phase changes from planning to implementation or review
- **THEN** the office scene changes agent positions, labels, or handoff indicators to show a different collaboration state
- **AND** the same state remains available through text labels

### Requirement: Reduced-Motion Fallback Is Mandatory

The control room MUST remain functional for users who prefer reduced motion, even if full-fidelity animation is deferred.

#### Scenario: Reduced-motion mode remains informative
- **WHEN** reduced motion is enabled through system preference or user choice
- **THEN** ambient animation is removed or minimized
- **AND** status remains clear through static or low-motion UI states

### Requirement: Reduced-Fidelity Pixel Skin Is An Allowed Tier 2 Degradation

The platform MUST preserve a documented Tier 2 degradation path in which a functional reduced-motion pixel-art skin ships before the full office-scene fidelity target is reached.

#### Scenario: Early GA uses reduced-fidelity control room
- **WHEN** the product uses the allowed Tier 2 control-room degradation path
- **THEN** the monitoring UI still preserves the pixel-art identity and status clarity
- **AND** the missing fidelity is tracked as a planned parity gap rather than a silent style change
