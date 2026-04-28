## Context

The Flow Simulator already has deterministic step metadata, 5 second slow-mode pacing, bundled PNG agent sprite sheets, and accessible text logs. The reference project, `the-dev-squad`, models five agents in a shared office with home positions, phase-specific collaboration positions, walking state, document handoffs, and speech bubbles.

This design adapts the reference behavior without adding Framer Motion. CSS transitions and a small frame timer are enough for the current Vite app.

## Goals / Non-Goals

**Goals:**

- Show all agents together in one pixel-art office scene.
- Move or orient agents based on the active simulator step.
- Make interactions visible: planner to reviewer, coder to tester, tester to reviewer, and PR creator handoff.
- Keep speech and status feedback deterministic and mirrored in accessible text.
- Preserve reduced-motion and browser-only simulator constraints.

**Non-Goals:**

- No backend runtime visualization feed.
- No tenant-uploaded sprite management.
- No full reference scene clone with every ambient behavior from `the-dev-squad`.
- No new animation library dependency.

## Decisions

- Create a local `DynamicPixelOffice` component.
  - Rationale: The office scene is substantial enough to isolate from simulator controls and logs.
  - Alternative considered: Keep all markup inside `FlowSimulator`. Rejected because it would make simulator state management harder to maintain.

- Use normalized scene coordinates and CSS transforms.
  - Rationale: This gives a stable office layout that scales across panel widths without canvas or SVG.
  - Alternative considered: Use canvas. Rejected because semantic text, tests, and responsive layout are simpler with DOM.

- Drive office state from simulation step metadata.
  - Rationale: The office must reflect the protected workflow path already validated by the simulator.
  - Alternative considered: Maintain a separate phase sequence. Rejected because it could drift from the graph steps.

- Use deterministic speech per agent and step.
  - Rationale: This keeps the didactic feedback testable and accessible.
  - Alternative considered: Random speech pools from the reference. Rejected for now because the simulator is a teaching aid and logs should remain stable.

## Risks / Trade-offs

- More visual complexity can reduce scanability - Mitigation: preserve concise text facts and the existing log.
- The office may feel less animated in reduced-motion mode - Mitigation: all current positions, labels, speech, and status remain visible.
- DOM animation may not match the reference exactly - Mitigation: copy the reference flow model and sprite-sheet treatment while avoiding a new dependency.

## Migration Plan

1. Add any needed bundled support assets from the reference sprite folder.
2. Extend simulator metadata with office phase and active role information.
3. Add `DynamicPixelOffice` and render it from the Flow Simulator.
4. Replace the prior single-agent visual stage with the office scene.
5. Update CSS and tests, then run OpenSpec validation, frontend tests, and frontend build.

Rollback is to remove the new office component and restore the prior single-agent stage.
