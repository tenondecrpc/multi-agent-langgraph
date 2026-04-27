## ADDED Requirements

### Requirement: Locale Extraction Tooling Maintains A Catalog Per Locale

The frontend build SHALL extract user-facing strings into per-locale JSON catalogs under `frontend/src/i18n/<locale>/`. English is the default shipped catalog. Spanish remains disabled by default per the documented Tier 2 degradation.

Extraction SHALL scan `frontend/src/features/`, `frontend/src/lib/`, and shared application shell components. Catalogs SHALL live under `frontend/src/i18n/locales/<locale>.json`; extraction output SHALL be normalized into `frontend/src/i18n/extracted/en.json` before comparison. User-facing strings in feature code SHALL use the localization helper rather than unmanaged literals, except for test fixtures, stable identifiers, and protocol constants.

CI SHALL fail when extraction finds new keys not present in the English catalog, when enabled locales are missing keys compared with English, or when existing key coverage regresses without an explicit review note. English remains the only enabled locale by default.

#### Scenario: Missing translation fails CI
- **WHEN** an extraction run finds new untranslated keys without a catalog update
- **THEN** the CI check fails with a list of missing keys

#### Scenario: Unmanaged literal fails extraction check
- **WHEN** a feature component adds user-visible text outside the localization helper
- **THEN** the locale extraction check fails
- **AND** the failure names the file and literal

### Requirement: Spanish Enablement Is A Configuration Toggle

Enabling the Spanish locale SHALL NOT require code changes. The toggle SHALL live in deploy-time configuration.

Spanish enablement SHALL be controlled by deploy-time configuration, defaulting to `en` only. The frontend SHALL load Spanish only when `FRONTEND_ENABLED_LOCALES` or the equivalent runtime config includes `es`. Missing Spanish keys SHALL fall back to English with a structured warning and a frontend error counter; fallback SHALL NOT hide CI coverage failures for enabled Spanish deployments.

#### Scenario: Spanish toggle without code change
- **WHEN** the Spanish locale is enabled at deploy time
- **THEN** the bundled catalog is loaded
- **AND** untranslated keys fall back to English with a logged warning

### Requirement: Component Accessibility Contract Tests Are Mandatory

Every `features/` directory SHALL contain at least one component-level test that validates keyboard reachability, AA contrast, no color-only state, and `prefers-reduced-motion` support.

The accessibility test contract SHALL use Vitest and Testing Library with repository-local helpers. Each feature test SHALL verify: all interactive controls are keyboard reachable, visible focus is present, state is represented by text or icon semantics in addition to color, text contrast meets WCAG AA, reduced-motion mode disables non-essential animation, live updates use an accessible announcement path, and error toasts are reachable and dismissible by keyboard.

#### Scenario: Reduced motion regression fails CI
- **WHEN** a component animates ignoring `prefers-reduced-motion`
- **THEN** the accessibility test fails the build

#### Scenario: Error toast is keyboard reachable
- **WHEN** a structured error toast is rendered
- **THEN** keyboard users can focus and dismiss it
- **AND** assistive technology can read severity, message, trace ID, and runbook link
