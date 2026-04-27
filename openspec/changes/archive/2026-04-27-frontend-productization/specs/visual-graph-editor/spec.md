## ADDED Requirements

### Requirement: Graph Editor Renders Shadow-Mode Preview

The graph editor SHALL fetch a candidate control-plane snapshot when one exists and render a side-by-side diff against the active snapshot. Added, removed, and changed nodes and routes SHALL be visually distinct.

Stage 1 SHALL remain read-only except for backend-routed preview and validation actions. The diff SHALL group `added`, `removed`, and `changed` nodes, edges, routes, interrupts, escalation sinks, role tool scopes, and protected workflow invariant changes. Validation feedback SHALL display backend rule identifiers, severity, affected node or edge, runbook or documentation link when present, and whether activation is blocked.

The editor SHALL support JSON export of active and candidate snapshots in stage 1. JSON import, direct node or edge editing, route editing, interrupt editing, and activation workflow UX are deferred to stage 2.

#### Scenario: Candidate snapshot present
- **WHEN** an operator opens the graph editor and a candidate snapshot exists
- **THEN** the diff view shows added, removed, and changed elements
- **AND** validation rule failures are surfaced inline

#### Scenario: No candidate snapshot
- **WHEN** no candidate snapshot exists
- **THEN** the editor renders the active snapshot in read-only mode
- **AND** a "no candidate" indicator is shown

#### Scenario: Protected invariant change is highlighted
- **WHEN** a candidate snapshot changes a protected route or removes a mandatory guard
- **THEN** the diff highlights the protected invariant change
- **AND** activation remains blocked by the backend validation result

### Requirement: Editor Never Substitutes For Backend Enforcement

The editor SHALL NOT mutate snapshots client-side. All activation flows SHALL go through the existing control-plane endpoints with shadow-mode validation.

#### Scenario: Activation routes through backend
- **WHEN** an operator activates a candidate snapshot
- **THEN** the activation request is sent to the control-plane endpoint
- **AND** the backend shadow-mode validation result governs the outcome

### Requirement: Full Visual Graph CRUD Remains A Deferred Parity Task

Full node, edge, route, interrupt CRUD, JSON import, keyboard editing model, activation workflow, and conflict handling SHALL remain a stage 2 parity follow-up. The stage 1 UI SHALL label the editor as read-only preview and SHALL link to the parity follow-up identifier when a user attempts direct editing.

#### Scenario: Direct edit attempt explains deferral
- **WHEN** an admin attempts to directly edit a node or edge in stage 1
- **THEN** the UI explains that full graph CRUD is deferred to stage 2
- **AND** no client-side mutation is persisted
