## ADDED Requirements

### Requirement: Operator Surfaces Render Live Backend Data

Every operator surface SHALL render data fetched from `/api/v1` rather than from local sample data. A feature flag SHALL allow temporary fallback to sample data for triage.

#### Scenario: Dashboard renders live tenant data
- **WHEN** an operator with a tenant-scoped role opens the dashboard
- **THEN** the surface fetches from `/api/v1/runtime/...` and `/api/v1/status-page`
- **AND** the tenant identifier is visible on the page

#### Scenario: Sample-data fallback is opt-in
- **WHEN** the operator triggers the sample-data fallback feature flag
- **THEN** the surface clearly displays a "sample data" badge

### Requirement: Errors Surface Runbook Links

Backend error payloads that include a `runbook_url` SHALL be rendered as a toast or inline alert that exposes the link to the operator.

#### Scenario: Persistence outage surfaces runbook
- **WHEN** the dashboard receives a `503` with a `runbook_url`
- **THEN** the toast includes a clickable runbook link
- **AND** the trace identifier is shown for support handoff

### Requirement: Accessibility Non-Negotiables Are Enforced At The Component Level

Each `features/` directory SHALL include at least one component-level accessibility test that validates keyboard reachability, no color-only state, AA contrast, and respect for `prefers-reduced-motion`.

#### Scenario: Color-only state regression fails CI
- **WHEN** a component encodes state using only color
- **THEN** the accessibility test fails the build
