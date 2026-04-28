# sprite-asset-management Specification

## Purpose
TBD - created by archiving change phase-6-operator-ui-and-control-room. Update Purpose after archive.
## Requirements
### Requirement: Bundled Reference Assets Are Supported

The frontend MUST support bundled sprite and scene assets that ship with the application. Bundled agent sprites MUST use the expected reference sprite sheets from `/Users/tenonde/Projects/open-sources/the-dev-squad/public/sprites` for planner, reviewer, coder, tester, and supervisor-style fallback roles.

Bundled reference assets MUST live in the planned frontend public asset area and be resolvable through stable manifests rather than hard-coded scattered paths.

#### Scenario: Bundled art lives with the frontend
- **WHEN** reference pixel-art assets are included with the product
- **THEN** the bundled assets live in the planned frontend public asset area
- **AND** later code can resolve them through stable manifests rather than hard-coded scattered paths

#### Scenario: Placeholder sprites are replaced

- **WHEN** the frontend bundled sprite manifest is loaded
- **THEN** planner, reviewer, coder, tester, and supervisor-style entries point to PNG sprite sheets copied from the declared reference project
- **AND** the previous placeholder SVG sprite entries are no longer referenced

### Requirement: Bundled Office Support Assets Are Available

The frontend MAY include bundled office support assets from the declared `the-dev-squad` reference project when those assets are used by the dynamic pixel office. These assets MUST remain static bundled assets and MUST NOT be treated as tenant-managed uploads.

#### Scenario: Office support assets are bundled

- **WHEN** the dynamic office references support assets such as furniture or activity props
- **THEN** those assets live under the frontend public asset area
- **AND** the upload-deferral behavior remains unchanged

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

### Requirement: Sprite Metadata CRUD Is Available To Admins

The system SHALL expose sprite metadata CRUD over an admin endpoint. The frontend SHALL render the catalog with role and state mappings.

Sprite metadata records SHALL include `sprite_id`, `display_name`, `asset_kind`, `bundled_asset_path`, optional `external_asset_ref`, `role_mappings`, `state_mappings`, `alt_text`, `reduced_motion_variant`, `tenant_id`, `team_id`, `enabled`, `created_by`, `updated_by`, `created_at`, and `updated_at`. Metadata CRUD SHALL be available only to authorized admins and super-admins, with backend RBAC remaining authoritative.

The bundled sprite catalog SHALL be served through the same metadata endpoint as tenant-managed metadata so the frontend does not need separate rendering logic. Tenant-managed upload remains disabled until the parity follow-up ships.

#### Scenario: Admin lists registered sprites
- **WHEN** a super admin opens the sprite admin surface
- **THEN** the catalog shows registered sprites, role mappings, and state mappings sourced from the admin endpoint

#### Scenario: Unauthorized user cannot edit sprite metadata
- **WHEN** a viewer attempts to update sprite metadata
- **THEN** the backend rejects the request
- **AND** the frontend renders a role-limited error state

### Requirement: Sprite Upload Returns 501 Until Parity Ships

Sprite upload SHALL return a `501 Not Implemented` response with a body that documents the deferred parity follow-up. The frontend SHALL render the same wording.

The 501 body SHALL include `error.code="sprite_upload_deferred"`, `message`, `parity_followup`, `runbook_url`, and `supported_alternative="bundled_sprite_metadata"`. The frontend SHALL keep metadata CRUD enabled while upload remains unavailable.

#### Scenario: Upload attempt yields 501 with parity link
- **WHEN** an admin attempts to upload a sprite
- **THEN** the API returns `501` with a body referencing the parity follow-up
- **AND** the frontend toast renders the same message

#### Scenario: Bundled sprites remain usable while upload is deferred
- **WHEN** upload returns `501`
- **THEN** bundled sprite metadata remains editable according to RBAC
- **AND** the control room continues resolving enabled bundled sprites
