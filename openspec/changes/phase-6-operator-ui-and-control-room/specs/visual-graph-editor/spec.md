## Non-Goals

- Defining low-level graph compiler code.
- Defining general-purpose arbitrary diagramming features.
- Defining the control-room visual art direction.

## ADDED Requirements

### Requirement: Graph Editor Reflects The Runtime Graph Contract

The graph editor MUST operate on the same graph configuration model and invariant rules defined by the backend control plane.

#### Scenario: Editor surfaces valid editable graph structure
- **WHEN** an admin opens the graph editor
- **THEN** the editor presents the current graph nodes, edges, routes, and interrupt points as governed by the backend config model
- **AND** editing actions are validated against the same protected invariants used for activation

### Requirement: Validation Feedback Is Immediate

The graph editor MUST surface validation errors and protected-node constraints before activation.

#### Scenario: Invalid edit is explained before activation
- **WHEN** an admin creates an invalid route or attempts to bypass a protected workflow invariant
- **THEN** the editor reports the validation failure with actionable feedback
- **AND** the invalid candidate cannot be activated as if it were safe

### Requirement: Read-Only Graph Visualization Is An Allowed Tier 2 Degradation

The platform MUST preserve a documented Tier 2 degradation path in which read-only graph visualization with JSON import and export can ship before full CRUD editing.

#### Scenario: Early GA ships visualization only
- **WHEN** the product uses the allowed Tier 2 degradation path for graph editing
- **THEN** admins can still inspect the graph and exchange config through structured import and export
- **AND** the lack of direct in-UI editing is recorded as a deliberate parity gap rather than an implicit omission
