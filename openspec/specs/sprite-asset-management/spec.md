# sprite-asset-management Specification

## Purpose
TBD - created by archiving change phase-6-operator-ui-and-control-room. Update Purpose after archive.
## Requirements
### Requirement: Bundled Reference Assets Are Supported

The frontend MUST support bundled sprite and scene assets that ship with the application.

#### Scenario: Bundled art lives with the frontend
- **WHEN** reference pixel-art assets are included with the product
- **THEN** the bundled assets live in the planned frontend public asset area
- **AND** later code can resolve them through stable manifests rather than hard-coded scattered paths

### Requirement: Tenant-Managed Assets Are Stored Outside The Container Filesystem

Tenant-uploaded or replaced assets MUST be stored durably outside the frontend container image and mapped through manifests.

#### Scenario: Uploaded asset persists durably
- **WHEN** an admin replaces a sprite or maps art to a runtime role or state
- **THEN** the asset is stored in durable object storage or an equivalent external store
- **AND** the container filesystem is not treated as the persistence layer for tenant-managed art

### Requirement: Upload Deferral Is An Allowed Tier 2 Degradation

The platform MUST preserve a documented Tier 2 degradation path in which bundled sprites ship first and upload endpoints return `501` until custom upload support is ready.

#### Scenario: Early GA defers custom upload
- **WHEN** the product uses the allowed Tier 2 sprite-upload degradation path
- **THEN** bundled assets remain usable for the control room
- **AND** upload attempts fail explicitly rather than appearing to succeed without persistence

