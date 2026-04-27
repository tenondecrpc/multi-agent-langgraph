## ADDED Requirements

### Requirement: Graph Editor Renders Shadow-Mode Preview

The graph editor SHALL fetch a candidate control-plane snapshot when one exists and render a side-by-side diff against the active snapshot. Added, removed, and changed nodes and routes SHALL be visually distinct.

#### Scenario: Candidate snapshot present
- **WHEN** an operator opens the graph editor and a candidate snapshot exists
- **THEN** the diff view shows added, removed, and changed elements
- **AND** validation rule failures are surfaced inline

#### Scenario: No candidate snapshot
- **WHEN** no candidate snapshot exists
- **THEN** the editor renders the active snapshot in read-only mode
- **AND** a "no candidate" indicator is shown

### Requirement: Editor Never Substitutes For Backend Enforcement

The editor SHALL NOT mutate snapshots client-side. All activation flows SHALL go through the existing control-plane endpoints with shadow-mode validation.

#### Scenario: Activation routes through backend
- **WHEN** an operator activates a candidate snapshot
- **THEN** the activation request is sent to the control-plane endpoint
- **AND** the backend shadow-mode validation result governs the outcome
