## ADDED Requirements

### Requirement: Operator Surfaces Render Live Backend Data

Every operator surface SHALL render data fetched from `/api/v1` rather than from local sample data. A feature flag SHALL allow temporary fallback to sample data for triage.

Typed clients SHALL be generated from the OpenAPI document served at `/api/v1/openapi.json`. CI SHALL normalize that document to `docs/api/openapi-v1.json`, regenerate client types into `frontend/src/api/generated/`, and fail when tracked generated files differ. Feature containers SHALL call generated clients through `frontend/src/api/client.ts` so auth headers, tenant context, trace IDs, error normalization, and sample-data fallback are handled consistently.

The generation contract SHALL use `openapi-typescript` unless an equivalent repository-standard generator is adopted in the follow-up implementation. Required scripts are `frontend:openapi:fetch`, `frontend:openapi:generate`, and `frontend:openapi:check`. Drift failure reason SHALL be `frontend_openapi_client_drift`; CI output SHALL list changed generated files and the OpenAPI source revision.

Live data surfaces SHALL use the following default cadences:

| Surface | Default cadence |
| --- | --- |
| Status page tile | 15 seconds |
| Dashboard run list | 30 seconds |
| Interrupts and DLQ | 10 seconds |
| Control room | 10 seconds |
| Graph editor | on open, manual refresh, after validation |
| Sprite admin | on open, manual refresh, after mutation |
| Billing | 5 minutes |
| Webhook admin | 60 seconds |
| Credentials and retention | 60 seconds |

Polling SHALL pause when the browser tab is hidden except for operator interrupt surfaces. Polling SHALL respect backend rate-limit responses and exponential backoff after repeated failures.

#### Scenario: Dashboard renders live tenant data
- **WHEN** an operator with a tenant-scoped role opens the dashboard
- **THEN** the surface fetches from `/api/v1/runtime/...` and `/api/v1/status-page`
- **AND** the tenant identifier is visible on the page

#### Scenario: Sample-data fallback is opt-in
- **WHEN** the operator triggers the sample-data fallback feature flag
- **THEN** the surface clearly displays a "sample data" badge

#### Scenario: OpenAPI client drift fails CI
- **WHEN** `/api/v1/openapi.json` changes and generated frontend clients are not regenerated
- **THEN** the frontend OpenAPI check fails with reason `frontend_openapi_client_drift`
- **AND** the failure lists the generated files that differ

#### Scenario: Rate limit slows polling
- **WHEN** a live data endpoint returns a rate-limit response
- **THEN** the polling hook backs off according to the response metadata
- **AND** the UI keeps the last successful data visible with a stale-data indicator

### Requirement: Errors Surface Runbook Links

Backend error payloads that include a `runbook_url` SHALL be rendered as a toast or inline alert that exposes the link to the operator.

Structured frontend errors SHALL include `severity`, `message`, `code`, `trace_id`, `runbook_url`, `feature`, and `retryable`. Toasts SHALL be keyboard reachable, dismissible, and available to assistive technology. Error text SHALL NOT expose credentials, raw webhook signatures, provider API keys, or customer payload bodies.

#### Scenario: Persistence outage surfaces runbook
- **WHEN** the dashboard receives a `503` with a `runbook_url`
- **THEN** the toast includes a clickable runbook link
- **AND** the trace identifier is shown for support handoff

#### Scenario: Error toast redacts sensitive details
- **WHEN** an API error includes a sensitive field or customer payload body
- **THEN** the frontend renders a redacted message
- **AND** the trace identifier remains available for support handoff

### Requirement: Accessibility Non-Negotiables Are Enforced At The Component Level

Each `features/` directory SHALL include at least one component-level accessibility test that validates keyboard reachability, no color-only state, AA contrast, and respect for `prefers-reduced-motion`.

#### Scenario: Color-only state regression fails CI
- **WHEN** a component encodes state using only color
- **THEN** the accessibility test fails the build

### Requirement: Role-Aware Empty States Preserve Tenant Context

Every live data surface SHALL render empty states that distinguish no matching data, insufficient role, missing tenant context, sample-data fallback, and backend unavailability. Tenant, team, role, active runtime profile, and data freshness SHALL be visible in the page chrome for every operator-facing screen. Screenshot export or support handoff flows SHALL redact tenant identifiers unless the export remains inside the customer-owned environment.

Role-aware navigation MAY hide actions a role cannot use, but backend authorization SHALL remain authoritative. The frontend SHALL NOT infer permission to mutate state only from visible UI.

#### Scenario: Viewer sees role-limited empty state
- **WHEN** a viewer opens a surface that requires operator privileges
- **THEN** the UI shows a role-limited empty state
- **AND** no privileged mutation control is rendered

#### Scenario: Tenant context is missing
- **WHEN** a tenant-scoped user has no tenant context in the session
- **THEN** live data fetching is blocked
- **AND** the UI shows a missing-tenant-context state with support guidance

### Requirement: Frontend Productization Implementation Is Deferred Until Specification Completion

Implementation of generated clients, feature split, polling hooks, structured toasts, role-aware empty states, sample-data feature flag, and CI OpenAPI regeneration checks SHALL be deferred to a follow-up OpenSpec apply pass. The follow-up implementation SHALL use this specification as the acceptance contract and SHALL include frontend tests and build verification.

#### Scenario: Specification phase completes without generated clients
- **WHEN** this OpenSpec change completes its artifact tasks
- **THEN** it may mark specification tasks complete without adding generated client code
- **AND** the next apply pass must implement generated clients before claiming frontend productization parity
