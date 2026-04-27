## Architecture Reuse

- Reuse the existing `/api/v1` surface and the OpenAPI document already produced by the API versioning change. No new API surface is introduced.
- Reuse role-aware navigation already present in the frontend shell.
- Reuse `vite`, `vitest`, and `@testing-library/react` already declared in `frontend/package.json`.
- Reuse the existing `frontend/src/i18n` scaffold for locale extraction.

## Module Layout

```
frontend/src/
  api/              generated typed clients per tag (runtime, status, billing, ...)
  features/
    dashboard/
    control-room/
    interrupts/
    graph-editor/
    sprites/
    knowledge/
    billing/
    webhook-admin/
    credentials/
    retention/
  i18n/
    en/
    es/             empty by default; populated when locale is enabled
  lib/
  test/
```

`features/<name>/` owns: route, container, polling hook, presentational components, tests, accessibility checks.

## Data Flow

- Each feature container uses a generated client.
- Polling cadence per surface is centrally configured; defaults are: status-page 15s, dashboard 30s, interrupts 10s, billing 5m, control room 10s.
- Errors render structured toasts that include `runbook_url` when present.
- Tenant context is read from the OIDC session and displayed on every screen so screenshots remain self-describing.

## Graph Editor Stages

Stage 1 (in scope here):
- Read-only graph rendering against the active control-plane snapshot.
- Shadow-mode preview that fetches a candidate snapshot and renders a side-by-side diff (added, removed, changed nodes; routing changes).
- Validation feedback surfaces existing graph rule violations.

Stage 2 (deferred):
- Node, edge, route, and interrupt CRUD.
- Activation flow with shadow-mode validation gate.

## Sprite Asset Management

- Metadata CRUD over an admin endpoint that lists registered sprites, role mappings, and state mappings.
- Upload is documented as 501 in line with the constitution Tier 2 degradation.
- Bundled sprite catalog is exposed through the same metadata endpoint to keep client logic uniform.

## Localization

- Extraction tooling extracts strings from `features/` and `lib/` to JSON catalogs under `i18n/<locale>/`.
- English is the shipped catalog. Spanish stays empty by default.
- A CI check fails when extraction reports new untranslated keys without a corresponding catalog update.
- Enabling Spanish at deploy time is a configuration toggle; no code change required.

## Accessibility Contract

- Component-level contract tests assert keyboard reachability, no color-only state, AA contrast, and `prefers-reduced-motion` honored.
- Each `features/` directory must include at least one accessibility test.

## Observability And Errors

- Errors surface a structured payload that the frontend renders with severity, message, runbook URL, and trace ID.
- A frontend-only counter `devsquad_frontend_errors_total{feature, severity}` is exposed via a backend reporter endpoint already present in the runtime contract for client-side error reporting.

## Protected Workflow Invariants

- The frontend never bypasses backend authorization. Role-aware navigation hides surfaces but does not authorize actions.
- Graph activation flows route through the existing control-plane endpoints with shadow-mode validation; no client-side enforcement substitutes for backend enforcement.
