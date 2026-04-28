## ADDED Requirements

### Requirement: Bundled Office Support Assets Are Available

The frontend MAY include bundled office support assets from the declared `the-dev-squad` reference project when those assets are used by the dynamic pixel office. These assets MUST remain static bundled assets and MUST NOT be treated as tenant-managed uploads.

#### Scenario: Office support assets are bundled

- **WHEN** the dynamic office references support assets such as furniture or activity props
- **THEN** those assets live under the frontend public asset area
- **AND** the upload-deferral behavior remains unchanged
