## Why

The frontend is the weakest leg of the system. `STATUS.md` records that live data is largely sample data, the graph editor is read-only, sprite upload is deferred (501), and localization is English-only. Only ~8 source files and 7 vitest cases exist. The constitution lists Tier 2 goals for the visual graph editor, sprite asset management, pixel-art control room, and Spanish localization, with explicit acceptable degradations - but the current frontend is below even the degraded baseline for live data integration.

This change does not aim for full Tier 2 parity in one shot. It defines the productization steps that move the UI from sample-data demo to a real operator surface backed by `/api/v1`, while keeping the documented Tier 2 degradations honest.

## What Changes

- Replace sample-data adapters with typed clients against the existing `/api/v1` surface (runtime, status-page, control-plane, knowledge admin, billing, webhook admin, credentials, data-retention).
- Define a typed API client generation contract sourced from `/api/v1/openapi.json`, regenerated in CI.
- Define live data refresh and polling cadences per surface (status, dashboard, interrupts, control room).
- Specify CRUD for sprite asset metadata while keeping bundled sprites as the default; upload itself remains deferred per Tier 2 degradation, but the API surface and UI scaffold must be present.
- Specify graph editor UX in two stages: stage 1 keeps read-only validation but adds shadow-mode preview; stage 2 (deferred) adds full node, edge, route, interrupt CRUD.
- Specify Spanish locale extraction infrastructure with English-only as the shipped default per the documented degradation, plus a path to enable Spanish without code changes.
- Specify accessibility non-negotiables already in the constitution (keyboard, no color-only state, `prefers-reduced-motion`, AA contrast) at the component contract level.
- Specify role-aware empty states, error toasts with runbook links, and tenant-context display.

## Capabilities

### Modified Capabilities

- `admin-and-monitoring-ui`: live data wiring, role-aware surfaces, error UX with runbook references.
- `visual-graph-editor`: shadow-mode preview now in scope; full editor remains a follow-up parity task.
- `sprite-asset-management`: metadata CRUD and UI scaffold; upload remains deferred to a parity follow-up.
- `frontend-accessibility-and-localization`: lock the accessibility non-negotiables at the component contract level; codify the locale extraction infrastructure even though Spanish ships disabled.

## Tier Classification

This change addresses Tier 2 capabilities and brings them up to (or beyond) the documented degraded floors. It does not weaken Tier 1.

## Non-Goals

- A new design system; reuse existing tokens.
- Mobile breakpoints beyond what the existing layout already supports.
- A WYSIWYG agent prompt editor; out of scope.
- A custom websocket transport; reuse polling and existing endpoints. Real-time streaming is a future change.

## Operational Impact

- CI gains a typed-client regeneration step that fails the build if the OpenAPI document drifts.
- Frontend bundle size grows; budget must be tracked in `vite.config.ts` build report.
- Operators see real tenant data; PII handling must respect existing role rules and retention.

## Risk

- Live data exposes tenant identifiers in screenshots; the spec must require redaction in support workflows.
- Polling at high cadence can pressure backend rate limits; cadences are bounded.
- Locale extraction without Spanish content can mask missing-translation regressions; CI must include a "missing translation" check that fails on coverage drop.

## Rollback / Degradation

- Each surface can fall back to its sample-data adapter via a feature flag for triage.
- Graph editor stage 1 stays read-only if shadow-mode preview is unstable.
- Spanish locale stays disabled by default; enabling it does not require a code change.
