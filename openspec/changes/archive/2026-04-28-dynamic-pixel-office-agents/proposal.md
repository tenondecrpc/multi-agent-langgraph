## Why

The current simulator shows a single active agent at a time, which improves clarity but still does not communicate that the squad works as a coordinated office. Operators need the pixel-art experience to show all agents together and make handoffs, reviews, tests, and PR creation visible as interactions between agents.

## What Changes

- Add a dynamic pixel office scene to the Flow Simulator where planner, reviewer, coder, tester, and PR creator are always visible.
- Map simulated pipeline steps to office phases, active agent groups, movement positions, facing direction, speech bubbles, and document handoffs.
- Reuse the `the-dev-squad` office flow concept: home desks, collaboration positions, active workers walking toward each other, and readable per-agent feedback.
- Keep all simulator behavior browser-only and read-only with no backend calls or runtime graph mutation.
- Preserve reduced-motion behavior by rendering the same office state without walking animation or automatic pacing.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `frontend-graph-flow-simulator`: Replace the single-agent stage with a multi-agent dynamic office stage tied to simulation steps.
- `pixel-art-control-room`: Move the product closer to the full-fidelity pixel-office target by using a reference-aligned office scene and interaction model.
- `sprite-asset-management`: Include bundled office support assets from the reference project when they are needed by the dynamic scene.

## Impact

- Affected code: frontend simulator components, simulator step metadata, styles, tests, and bundled sprite assets.
- No backend APIs, database schema, graph execution, RBAC, Kubernetes, Helm, secrets, or persistence behavior changes.
- Tier 1 non-negotiables remain unchanged. This touches Tier 2 pixel-art control room and bundled sprite degradation goals.
- Operational risk is limited to frontend rendering. Rollback is to remove the dynamic office component and restore the single-agent simulator stage from the prior change.
