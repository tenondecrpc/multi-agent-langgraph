## ADDED Requirements

### Requirement: Model Catalog Of Record Lives In PostgreSQL With A Bundled Air-Gapped Fallback

The model catalog SHALL be authoritative in PostgreSQL. The container image SHALL ship a bundled YAML catalog that the adapter reconciles against on boot so air-gapped deployments remain functional.

#### Scenario: Boot reconciliation in connected mode
- **WHEN** a connected deployment starts
- **THEN** the adapter reconciles the bundled YAML against the PostgreSQL catalog
- **AND** differences are logged as reconciliation events with actor `system:boot`

#### Scenario: Boot reconciliation in air-gapped mode
- **WHEN** an air-gapped deployment starts and PostgreSQL is empty
- **THEN** the adapter seeds the catalog from the bundled YAML
- **AND** subsequent admin updates to the catalog persist to PostgreSQL and are audited
