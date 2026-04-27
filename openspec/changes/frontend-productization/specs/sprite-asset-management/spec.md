## ADDED Requirements

### Requirement: Sprite Metadata CRUD Is Available To Admins

The system SHALL expose sprite metadata CRUD over an admin endpoint. The frontend SHALL render the catalog with role and state mappings.

#### Scenario: Admin lists registered sprites
- **WHEN** a super admin opens the sprite admin surface
- **THEN** the catalog shows registered sprites, role mappings, and state mappings sourced from the admin endpoint

### Requirement: Sprite Upload Returns 501 Until Parity Ships

Sprite upload SHALL return a `501 Not Implemented` response with a body that documents the deferred parity follow-up. The frontend SHALL render the same wording.

#### Scenario: Upload attempt yields 501 with parity link
- **WHEN** an admin attempts to upload a sprite
- **THEN** the API returns `501` with a body referencing the parity follow-up
- **AND** the frontend toast renders the same message
