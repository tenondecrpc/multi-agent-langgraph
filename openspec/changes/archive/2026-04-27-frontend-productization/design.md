## Architecture Reuse

- Reuse the existing `/api/v1` surface and the OpenAPI document already produced by the API versioning change. No new API surface is introduced.
- Reuse role-aware navigation already present in the frontend shell.
- Reuse `vite`, `vitest`, and `@testing-library/react` already declared in `frontend/package.json`.
- Reuse the existing `frontend/src/i18n` scaffold for locale extraction.

## Module Layout

```
frontend/src/
  api/
    generated/      generated schemas and operation types
    client.ts       typed fetch wrapper, auth headers, error normalization
    polling.ts      central cadence registry
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

The typed client is generated from the live backend OpenAPI document served at `/api/v1/openapi.json`. CI stores a normalized copy at `docs/api/openapi-v1.json`, runs the generator into `frontend/src/api/generated/`, and fails if regeneration changes tracked files. The follow-up implementation SHALL add the generator dev dependency and scripts, with `openapi-typescript` as the preferred generator unless a repository-standard alternative is already present.

## Data Flow

- Each feature container uses a generated client.
- Polling cadence per surface is centrally configured.
- Errors render structured toasts that include `runbook_url` when present.
- Tenant context is read from the OIDC session and displayed on every screen so screenshots remain self-describing.

| Surface | Endpoints | Default cadence | Pause behavior |
| --- | --- | --- | --- |
| Status page tile | `/api/v1/status-page` | 15 seconds | pause while tab hidden |
| Dashboard run list | `/api/v1/runtime/...` | 30 seconds | pause while tab hidden, refresh on focus |
| Interrupts and DLQ | `/api/v1/runtime/...` | 10 seconds | keep polling for operators and admins |
| Control room | `/api/v1/runtime/...`, `/api/v1/status-page` | 10 seconds | honor reduced-motion and tab visibility |
| Graph editor | control-plane snapshot endpoints | on open, manual refresh, after validation | no background polling |
| Sprite admin | sprite metadata admin endpoint | on open, manual refresh, after mutation | no background polling |
| Billing | billing export and summary endpoints | 5 minutes | refresh on focus |
| Webhook admin | webhook and idempotency admin endpoints | 60 seconds | pause while tab hidden |
| Credentials and retention | credentials, DPA, retention endpoints | 60 seconds | refresh on focus |

Role-aware empty states SHALL distinguish "no data exists" from "role cannot view this data" and "tenant context missing". Every operator screenshot SHALL display tenant, team, role, active runtime profile, and sample-data status. Support workflows SHALL redact tenant identifiers when exporting screenshots outside the customer-owned environment.

## Graph Editor Stages

Stage 1 (in scope here):
- Read-only graph rendering against the active control-plane snapshot.
- Shadow-mode preview that fetches a candidate snapshot and renders a side-by-side diff (added, removed, changed nodes; routing changes).
- Validation feedback surfaces existing graph rule violations.
- Diff rendering groups `added`, `removed`, and `changed` nodes, edges, routes, interrupts, escalation sinks, and protected-invariant changes.
- Candidate activation remains a backend action; the frontend only displays backend validation and shadow-mode results.

Stage 2 (deferred):
- Node, edge, route, and interrupt CRUD.
- Activation flow with shadow-mode validation gate.
- Parity follow-up: full visual CRUD, JSON import/export, route editing, interrupt editing, keyboard editing model, and activation workflow.

## Sprite Asset Management

- Metadata CRUD over an admin endpoint that lists registered sprites, role mappings, and state mappings.
- Upload is documented as 501 in line with the constitution Tier 2 degradation.
- Bundled sprite catalog is exposed through the same metadata endpoint to keep client logic uniform.
- Metadata records include sprite id, display name, bundled asset path or external asset reference, role mapping, state mapping, alt text, reduced-motion variant, tenant scope, created/updated audit fields, and enabled flag.
- Upload attempts return a structured 501 body with `error.code`, `message`, `parity_followup`, and `runbook_url`.

## Localization

- Extraction tooling extracts strings from `features/` and `lib/` to JSON catalogs under `i18n/<locale>/`.
- English is the shipped catalog. Spanish stays empty by default.
- A CI check fails when extraction reports new untranslated keys without a corresponding catalog update.
- Enabling Spanish at deploy time is a configuration toggle; no code change required.
- Catalogs live under `frontend/src/i18n/locales/<locale>.json`; extraction writes `frontend/src/i18n/extracted/en.json` and compares keys against shipped catalogs.
- Spanish is controlled by deploy-time config `FRONTEND_ENABLED_LOCALES`, defaulting to `en`.

## Accessibility Contract

- Component-level contract tests assert keyboard reachability, no color-only state, AA contrast, and `prefers-reduced-motion` honored.
- Each `features/` directory must include at least one accessibility test.
- Tests use Vitest, Testing Library, and repository-local helpers for contrast and reduced-motion checks.

## Observability And Errors

- Errors surface a structured payload that the frontend renders with severity, message, runbook URL, and trace ID.
- A frontend-only counter `devsquad_frontend_errors_total{feature, severity}` is exposed via a backend reporter endpoint already present in the runtime contract for client-side error reporting.

## Protected Workflow Invariants

- The frontend never bypasses backend authorization. Role-aware navigation hides surfaces but does not authorize actions.
- Graph activation flows route through the existing control-plane endpoints with shadow-mode validation; no client-side enforcement substitutes for backend enforcement.
