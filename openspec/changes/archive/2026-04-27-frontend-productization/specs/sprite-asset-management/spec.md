## ADDED Requirements

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
