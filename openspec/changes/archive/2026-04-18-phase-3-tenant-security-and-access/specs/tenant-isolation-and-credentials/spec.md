## Non-Goals

- Defining queue algorithms, autoscaling, or sandbox lifecycle.
- Defining billing exports or LLM routing policy.
- Defining frontend layout or interaction patterns.

## ADDED Requirements

### Requirement: Tenant And Team Isolation Boundaries

The product MUST enforce tenant and team isolation across repository scope, credentials, data visibility, memory, and budget ownership.

#### Scenario: Repository scope stays team-bound
- **WHEN** a run is created for a team
- **THEN** repository access is limited to the repositories allowed for that team
- **AND** the run cannot expand its repository scope by reading or writing another team's repositories

#### Scenario: Visibility stays tenant-scoped
- **WHEN** users query jobs, metrics, or streams
- **THEN** they only receive data for their tenant and authorized teams
- **AND** cross-tenant visibility is reserved only for explicit super-admin operational surfaces

### Requirement: Credentials Are Service-Layer Secrets

Credentials MUST remain service-layer material, never part of the LLM context, and MUST be isolated per team or stronger boundary.

#### Scenario: Runtime retrieves credentials without exposing them to the model
- **WHEN** the service resolves GitHub, Jira, or provider credentials for a run
- **THEN** those secrets are accessed by the service and tool layers only
- **AND** they are not inserted into prompts, model context, frontend bundles, or logs

#### Scenario: Credential scope remains team-specific
- **WHEN** multiple teams operate within the same tenant deployment
- **THEN** each team uses its own credential set or stricter boundary
- **AND** one team's run cannot borrow another team's write credentials

### Requirement: Envelope Encryption And Rotation Are Mandatory

Stored credentials MUST be envelope-encrypted with tenant-scoped key hierarchy and MUST follow a bounded rotation policy.

#### Scenario: Stored credentials remain encrypted at rest
- **WHEN** credential material is persisted in PostgreSQL or delivered to workloads
- **THEN** the credential payload is stored as ciphertext protected by tenant-scoped key material
- **AND** plaintext credentials do not live in committed configuration, ConfigMaps, or long-lived logs

#### Scenario: Overdue rotation blocks new runs
- **WHEN** a credential set passes its allowed rotation window
- **THEN** the system marks the credential set as overdue
- **AND** new runs for that scope may be blocked until rotation is completed or an explicit break-glass procedure is invoked

### Requirement: GitHub App Is The Default Integration Identity

GitHub App installation tokens MUST be the default integration path, while PAT usage remains an explicit and more restricted fallback.

#### Scenario: Standard onboarding uses GitHub App
- **WHEN** a team configures GitHub access for normal operation
- **THEN** the default path uses GitHub App installation tokens minted on demand
- **AND** long-lived PATs are not treated as the preferred baseline

#### Scenario: PAT fallback is clearly constrained
- **WHEN** a tenant cannot use a GitHub App and opts into PAT mode
- **THEN** the tenant is flagged for stricter policy and audit treatment
- **AND** PAT mode does not weaken repository safety or branch-protection checks
