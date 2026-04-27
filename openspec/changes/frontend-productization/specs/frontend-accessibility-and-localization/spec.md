## ADDED Requirements

### Requirement: Locale Extraction Tooling Maintains A Catalog Per Locale

The frontend build SHALL extract user-facing strings into per-locale JSON catalogs under `frontend/src/i18n/<locale>/`. English is the default shipped catalog. Spanish remains disabled by default per the documented Tier 2 degradation.

#### Scenario: Missing translation fails CI
- **WHEN** an extraction run finds new untranslated keys without a catalog update
- **THEN** the CI check fails with a list of missing keys

### Requirement: Spanish Enablement Is A Configuration Toggle

Enabling the Spanish locale SHALL NOT require code changes. The toggle SHALL live in deploy-time configuration.

#### Scenario: Spanish toggle without code change
- **WHEN** the Spanish locale is enabled at deploy time
- **THEN** the bundled catalog is loaded
- **AND** untranslated keys fall back to English with a logged warning

### Requirement: Component Accessibility Contract Tests Are Mandatory

Every `features/` directory SHALL contain at least one component-level test that validates keyboard reachability, AA contrast, no color-only state, and `prefers-reduced-motion` support.

#### Scenario: Reduced motion regression fails CI
- **WHEN** a component animates ignoring `prefers-reduced-motion`
- **THEN** the accessibility test fails the build
