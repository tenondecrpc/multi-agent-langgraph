# api-surface-and-versioning Specification

## Purpose
TBD - created by archiving change phase-2-platform-and-sandbox. Update Purpose after archive.
## Requirements
### Requirement: Versioned Public API Surface

The product MUST expose a versioned public API under `/api/v1` and MUST maintain a published OpenAPI contract with compatibility checks.

#### Scenario: Public routes are organized by version
- **WHEN** backend APIs are planned for status, admin, metering, or graph operations
- **THEN** they are defined under `/api/v1`
- **AND** versionless internal-only routes are not used as the public contract surface

#### Scenario: Contract changes are diff-gated
- **WHEN** a future change modifies the published API schema
- **THEN** the change is checked against the prior OpenAPI contract
- **AND** backward-incompatible changes require an explicit versioning or deprecation path

### Requirement: Endpoint Categories Match Product Responsibilities

The public surface MUST include explicit categories for webhook intake, status and stream APIs, auth callback, admin APIs, and metering export surfaces.

#### Scenario: Endpoint inventory remains aligned with the product
- **WHEN** operators and frontend clients integrate with the product
- **THEN** they can discover dedicated surfaces for webhook intake, execution status, SSE streaming, OIDC callback, admin control, and metering export
- **AND** those surfaces do not require hidden or ad hoc endpoints outside the published inventory

### Requirement: Deprecation Policy Is Published

The public API MUST define a deprecation window and expectations for clients upgrading across compatible versions.

#### Scenario: Deprecated behavior remains predictable
- **WHEN** an endpoint or response field must be retired
- **THEN** the deprecation is announced through the documented API policy
- **AND** clients receive a bounded transition window rather than an unannounced breaking removal

