## Why

The product includes a tenant-scoped operator surface, a pixel-art control room, a graph editor, sprite management, and accessibility commitments that go beyond a generic admin dashboard. `docs/PLAN.md` needs to be decomposed into explicit UI capabilities so later implementation can preserve both the operational requirements and the intended visual direction.

## What Changes

- Define the role-aware admin and monitoring UI for dashboard, interrupts, DLQ, cost views, agent config management, and test-agent workflows.
- Define the visual graph editor capability and its allowed Tier 2 read-only degradation path.
- Define the pixel-art control room, copy-first visual direction, and multi-ticket monitoring expectations.
- Define sprite asset management for bundled and tenant-uploaded assets, including the allowed Tier 2 upload degradation path.
- Define accessibility and localization requirements, including the WCAG non-negotiable subset and the English-only degradation path for early GA.
- Add a first executable frontend slice that ships role-aware monitoring, a reduced-motion control room, bundled sprite assets, and a read-only graph editor with JSON import and export while explicitly using the allowed Tier 2 degradations for direct graph CRUD, tenant sprite upload, and English-only GA.
- Classify this phase as mixed Tier 1 and Tier 2: access scoping and accessibility subset are mandatory, while graph editor editing, sprite upload, full-fidelity control room, and full Spanish localization retain the documented degradation paths.

## Capabilities

### New Capabilities
- `admin-and-monitoring-ui`: Role-aware monitoring, dashboard, interrupts, DLQ management, cost views, agent config CRUD, and test-agent surfaces.
- `visual-graph-editor`: Graph visualization and editing, validation feedback, activation flow, and read-only degradation path.
- `pixel-art-control-room`: Control-room visual direction, multi-ticket status representation, motion behavior, and fidelity bar.
- `sprite-asset-management`: Bundled sprite assets, tenant-uploaded replacements, role or state mapping, and object-storage expectations.
- `frontend-accessibility-and-localization`: WCAG obligations, reduced motion, live narration, keyboard coverage, and localization requirements with allowed degradation.

### Modified Capabilities
- None.

## Impact

- Future `frontend/` route and component planning.
- Backend admin and monitoring APIs that support the UI surfaces.
- Asset storage and manifest planning.
- QA, accessibility, and localization verification work in later phases.
- Frontend verification now includes `npm run --prefix frontend test -- --run` and `npm run --prefix frontend build` before this change can be archived.
