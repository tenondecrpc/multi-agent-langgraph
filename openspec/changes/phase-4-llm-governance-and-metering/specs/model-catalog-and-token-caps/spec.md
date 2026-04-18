## Non-Goals

- Defining cost dashboards or UI forms.
- Defining prompt content or review logic.
- Defining PostgreSQL schema details beyond the validation contract.

## ADDED Requirements

### Requirement: Model IDs Come From A Pinned Catalog

Configured model identifiers MUST resolve against a pinned catalog rather than silently accepting arbitrary strings.

#### Scenario: Unknown model ID fails validation
- **WHEN** an admin or config change references an unknown model identifier
- **THEN** the configuration is rejected during validation
- **AND** the runtime does not silently substitute a different model

### Requirement: Token Ceilings Are Role-Aware

The runtime MUST derive request and response token ceilings from both the pinned model catalog and the role-specific guardrails.

#### Scenario: Effective token ceiling is clamped
- **WHEN** a role uses a model with a large context window
- **THEN** the effective input and output ceilings are limited by the smaller of the model limit and the role policy limit
- **AND** optional tenant overrides may tighten those ceilings but may not exceed the model boundary

### Requirement: Air-Gapped Catalog Remains Explicit

The air-gapped profile MUST define its own allowed catalog entries rather than relying on connected-environment defaults.

#### Scenario: Air-gapped fallback stays self-hosted
- **WHEN** an air-gapped deployment configures primary and fallback models
- **THEN** both model IDs resolve to the self-hosted catalog approved for that environment
- **AND** connected-environment provider identifiers are not accepted as valid fallbacks there
