## Context

The frontend already has a browser-only Flow Simulator and a reduced-fidelity control room. The current sprites are placeholder SVG files and the simulator's slow mode advances every 1000 ms. The requested reference implementation in `the-dev-squad` uses PNG sprite sheets for agents, CSS background-position frame selection, speech bubbles, active glow, and movement timing that gives users time to understand each agent's work.

This change is frontend-only. It does not alter runtime graph execution, backend APIs, persistence, RBAC, tenant boundaries, Helm, Kubernetes, secrets, or operational control planes.

## Goals / Non-Goals

**Goals:**

- Replace current placeholder SVG sprites with the expected PNG sprite sheets from `the-dev-squad`.
- Render active simulated agents visually in the Flow Simulator with speech text that mirrors the deterministic step narration.
- Pace automatic slow-mode advancement at 5000 ms per agent step.
- Preserve read-only, browser-only simulator behavior with no backend calls or graph mutations.
- Preserve accessibility requirements: keyboard controls, visible text state, `aria-live` logs, no color-only state, and reduced-motion fallback.

**Non-Goals:**

- No sprite upload parity work. Upload remains explicitly deferred with the current 501 behavior.
- No backend sprite metadata CRUD changes.
- No full office-scene parity implementation.
- No changes to runtime LangGraph orchestration or PR creation behavior.

## Decisions

- Use the `the-dev-squad` PNG sprite sheets as bundled frontend assets.
  - Rationale: The user identified these as the expected assets, and they match the reference animation model.
  - Alternative considered: Generate new SVG or CSS sprites. Rejected because it would diverge from the requested reference.

- Implement sprite animation with CSS background-position and a small React component-local frame timer.
  - Rationale: The existing Vite app does not depend on Framer Motion, and this animation can be implemented without adding a dependency.
  - Alternative considered: Add Framer Motion to mirror the reference component exactly. Rejected because the current need is limited and a new dependency is not justified.

- Keep step narration deterministic and reuse it for both speech bubbles and the live text log.
  - Rationale: The simulator remains didactic and testable, and screen-reader users receive the same feedback as sighted users.
  - Alternative considered: Random speech pools from the reference. Rejected because deterministic simulator output is easier to test and audit.

- Change the slow-mode delay constant from 1000 ms to 5000 ms.
  - Rationale: A 5 second per-agent delay gives operators enough time to read the current agent feedback.
  - Alternative considered: Make delay configurable. Rejected for this change because the user asked for a fixed 5 second delay.

## Risks / Trade-offs

- Larger bundled assets increase frontend static payload modestly - Mitigation: include only the required agent PNG sprite sheets, not every furniture asset from the reference.
- Animation can distract some users - Mitigation: the existing reduced-motion toggle pauses automatic pacing and keeps manual Step controls available.
- Sprite-sheet assumptions can break if the reference assets change shape - Mitigation: keep dimensions and frame constants local and covered by tests that assert expected manifest paths and visual metadata.
- Placeholder asset deletion can break old manifest references - Mitigation: update the manifest and sample data in the same change.

## Migration Plan

1. Remove the current placeholder SVG sprite files from `frontend/public/assets/sprites`.
2. Copy `agent_a.png`, `agent_b.png`, `agent_c.png`, `agent_d.png`, and `agent_s.png` from `the-dev-squad` into the same bundled asset directory.
3. Update the bundled manifest and frontend sample data to use the new PNG paths.
4. Update the Flow Simulator UI, styles, copy, and tests for visual agent feedback and 5000 ms pacing.
5. Verify with frontend tests and build.

Rollback is to restore the previous placeholder SVG files, manifest entries, simulator markup, and 1000 ms test expectation.

## Open Questions

- None for this scope.
