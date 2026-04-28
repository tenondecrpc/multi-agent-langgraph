## Why

The current frontend uses placeholder sprite assets and a minimal step strip that does not match the expected visual reference from `the-dev-squad`. Operators need a more didactic, visual simulation that shows what each agent is doing while preserving the browser-only simulator guardrails.

## What Changes

- Replace the current bundled placeholder SVG sprites with PNG sprite sheets copied from `/Users/tenonde/Projects/open-sources/the-dev-squad/public/sprites`.
- Update the Flow Simulator to render animated pixel agents with speech feedback for the active simulated step.
- Change slow automatic advancement from the existing 1 second cadence to a 5 second per-agent cadence.
- Keep reduced-motion behavior text-first and user-driven through the Step button.
- Preserve the simulator as read-only, browser-only, and disconnected from backend runtime execution.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `frontend-graph-flow-simulator`: Change the automatic visual pacing and require agent-level visual feedback for simulated steps.
- `sprite-asset-management`: Replace bundled placeholder assets with the expected reference sprite sheets and update stable manifest paths.
- `pixel-art-control-room`: Keep the visual direction aligned with the declared pixel-art reference by reusing the expected agent sprite sheets.

## Impact

- Affected code: `frontend/src/components/FlowSimulator.tsx`, `frontend/src/lib/graphSimulator.ts`, `frontend/src/data/sampleData.ts`, `frontend/src/i18n/messages.ts`, `frontend/src/styles.css`, and frontend tests.
- Affected assets: `frontend/public/assets/sprites/` placeholder SVGs are removed and replaced with PNG sprite sheets from `the-dev-squad`.
- No backend APIs, database schemas, runtime graph execution, Kubernetes resources, Helm values, secrets, RBAC, or deployment topology are changed.
- Tier 1 non-negotiables are preserved. This change touches Tier 2 pixel-art control room and sprite upload degradation goals only, using bundled assets while upload remains deferred.
- Operational risk is limited to frontend rendering. Rollback is to restore the previous placeholder asset manifest and simulator pacing.
