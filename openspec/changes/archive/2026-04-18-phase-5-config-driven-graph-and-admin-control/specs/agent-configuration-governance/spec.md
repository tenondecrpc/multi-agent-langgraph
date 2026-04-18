## Non-Goals

- Defining the UI form layout for admin editing.
- Defining human staffing or approval policies.
- Defining provider invoice reconciliation behavior.

## ADDED Requirements

### Requirement: Agent Config Is Role-Bound And Validated

Each agent configuration MUST be validated against its role boundary, including allowed tools, model settings, and retry fields.

#### Scenario: Invalid tool grant is rejected
- **WHEN** an admin attempts to configure a role with tools outside its approved whitelist
- **THEN** validation rejects the configuration
- **AND** the platform does not rely on frontend hints alone to prevent the invalid grant

#### Scenario: Role config includes required operational fields
- **WHEN** a valid agent configuration is stored
- **THEN** it includes the role, model, fallback model, system prompt, allowed tools, and retry-related settings required by that role

### Requirement: Agent Testing Respects Production Guardrails

Dry-run or test-agent workflows MUST obey the same validation and least-privilege constraints as normal agent configuration.

#### Scenario: Test-agent request stays within policy
- **WHEN** an admin sends a dry-run or test request to an agent configuration
- **THEN** the request uses the validated model and tool boundaries for that role
- **AND** the test surface does not become a side door for unreviewed privileges

### Requirement: Default Role Mapping Remains Available

The product MUST support a default model mapping per role even when admins later override settings.

#### Scenario: New deployment starts with default role mapping
- **WHEN** a tenant initializes the product without custom per-role model overrides
- **THEN** the platform provides the documented default role-to-model mapping
- **AND** later overrides are optional refinements rather than a requirement for basic operation
