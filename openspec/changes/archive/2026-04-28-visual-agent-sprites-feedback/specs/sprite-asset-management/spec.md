## MODIFIED Requirements

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
