# api-versioning-and-compatibility Specification

## Purpose
Define the public API versioning, compatibility, deprecation, streaming schema, and metering export lifecycle rules.

## Requirements

### Requirement: Path-Based API Versioning

All public API routes SHALL use a `/api/v<major>/` prefix. Unversioned paths SHALL NOT be accepted except during a transition redirect window declared in configuration.

#### Scenario: Unversioned path is redirected or rejected
- **WHEN** a request arrives on an unversioned path
- **THEN** it is either redirected to the current major during the transition window or rejected with 404 after the window

### Requirement: CI OpenAPI Diff Gate

Pull requests SHALL pass an `openapi-diff` step comparing the branch OpenAPI to main. Breaking changes SHALL block the merge unless the PR carries a super_admin-issued `breaking-change-approved` label with recorded rationale.

#### Scenario: Removed endpoint blocks merge
- **WHEN** a PR removes or narrows a public endpoint without approval
- **THEN** CI blocks the merge
- **AND** the diff report is attached to the PR

### Requirement: Deprecation And Sunset Headers

Deprecated routes SHALL emit `Deprecation: true` and `Sunset: <ISO-date>` response headers and SHALL log a structured deprecation event with tenant, route, and client identity hints.

#### Scenario: Deprecated route call logs structured event
- **WHEN** a client calls a deprecated route
- **THEN** the response carries `Deprecation` and `Sunset` headers
- **AND** the backend logs `api_deprecation_hit` with tenant_id and route

### Requirement: Accept-Version Negotiation And SSE Schema Version

The backend SHALL honor `Accept-Version` when multiple majors are active. SSE streams SHALL emit a `schema_version` event so clients can lock to a compatible schema.

#### Scenario: Client pins to a major via Accept-Version
- **WHEN** a client sends `Accept-Version: 1`
- **THEN** the response uses the v1 schema
- **AND** no implicit upgrade to a newer major occurs

### Requirement: Metering Export 12-Month Parallel Support

Metering exports SHALL emit each new schema version alongside the previous version for at least 12 months. Each version SHALL be served on distinct paths.

#### Scenario: v1 remains available after v2 ships
- **WHEN** v2 metering export ships
- **THEN** v1 continues to produce for at least 12 months
- **AND** sunset is announced via headers and docs
