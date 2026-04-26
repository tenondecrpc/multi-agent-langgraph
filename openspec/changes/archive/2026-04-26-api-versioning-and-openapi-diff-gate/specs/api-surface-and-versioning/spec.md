## ADDED Requirements

### Requirement: Diff-Gate Enforcement Is Not Bypassable Without Super Admin

The `openapi-diff` CI step SHALL be required on all public-API-touching PRs. Bypass SHALL require an explicit super_admin-issued label with recorded rationale and SHALL emit an audit event.

#### Scenario: Bypass without approval fails
- **WHEN** a PR attempts to bypass the gate without the super_admin label
- **THEN** CI blocks the merge
- **AND** the attempt is logged for audit
