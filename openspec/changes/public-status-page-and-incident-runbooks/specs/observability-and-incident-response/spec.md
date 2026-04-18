## ADDED Requirements

### Requirement: Runbook Corpus Is Versioned Alongside Alert Rules

Runbooks SHALL live under `docs/runbooks/` and SHALL be versioned together with the alert rules they accompany. Deleting an alert without deleting or updating its runbook SHALL be blocked by CI.

#### Scenario: Orphaned runbook warns
- **WHEN** a runbook exists without a referencing alert
- **THEN** CI raises a warning with the orphan file list
