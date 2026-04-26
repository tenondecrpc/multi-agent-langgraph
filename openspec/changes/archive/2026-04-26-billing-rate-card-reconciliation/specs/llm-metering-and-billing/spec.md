## ADDED Requirements

### Requirement: Metering Facts Carry Provider Request Id

`llm_usage` (or the equivalent metering facts table) SHALL include `provider_request_id` nullable, populated when available, used by reconciliation.

#### Scenario: New usage writes capture provider_request_id
- **WHEN** a new LLM call records usage
- **THEN** the `provider_request_id` is captured if provided by the LLM response
- **AND** observability distinguishes captured versus missing counts
