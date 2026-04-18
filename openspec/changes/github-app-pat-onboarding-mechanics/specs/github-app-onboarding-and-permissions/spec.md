## ADDED Requirements

### Requirement: GitHub App Is The Default Integration Path

The backend SHALL use GitHub App installations as the default GitHub integration path. Installation tokens MUST be minted on demand, have a maximum TTL of 60 minutes, and MUST NOT be persisted.

#### Scenario: Tenant installs the GitHub App
- **WHEN** a super_admin completes the installation wizard
- **THEN** a `github_app_installations` row is created with installation_id, account_login, and permissions_hash
- **AND** an audit event is emitted

#### Scenario: Installation token is minted on demand
- **WHEN** the pr_creator node needs to call GitHub
- **THEN** the backend mints an installation token using the App private key from Vault
- **AND** the token is used for that request only and never persisted

### Requirement: PAT Usage Is Explicit Opt-In And More Restricted

The backend SHALL permit PAT usage only after an audited super_admin opt-in that records actor, rationale, allowed scopes, and expires_at. PAT mode SHALL surface a persistent admin-UI banner and apply stricter per-tenant rate limits.

#### Scenario: PAT opt-in is audited
- **WHEN** a super_admin opts a tenant into PAT mode
- **THEN** a `pat_opt_ins` row is created with full metadata
- **AND** the admin UI displays a PAT-mode banner that meets the AA contrast and keyboard reachability non-negotiables

#### Scenario: PAT mode applies stricter rate limits
- **WHEN** a tenant is in PAT mode
- **THEN** the GitHub integration rate limit is lower than the App limit
- **AND** the credential-rotation SLA applies to the PAT age

### Requirement: Least-Privilege Permission Set Is Enforced

The backend SHALL request only the least-privilege GitHub App permissions required for its documented operations and SHALL block any call that would require a permission outside the granted set.

#### Scenario: Missing permission is detected and blocked
- **WHEN** an operation requires a permission not present on the installation
- **THEN** the operation fails closed with a typed permission error
- **AND** the event is logged and visible in the admin UI

### Requirement: Permission Drift Is Detected And Alerted

The backend SHALL periodically reconcile each installation's current permission set against the expected least-privilege hash and SHALL block new mint calls until drift is acknowledged by super_admin.

#### Scenario: Drift raises an incident
- **WHEN** the reconciliation detects a permission change
- **THEN** a `github_permission_drift` event is emitted
- **AND** mint calls for that installation fail until acknowledgement

### Requirement: Branch-Protection Verification Before PR Creation

The backend SHALL verify branch-protection settings before creating a PR, including required status checks, required reviews, required signed commits when configured, and linear-history when configured. Missing required protection SHALL block PR creation and SHALL route to the `security_review` escalation sink.

#### Scenario: Required checks absent blocks PR creation
- **WHEN** branch protection lacks a required status check
- **THEN** the pr_creator node does not open a PR
- **AND** the run pauses with escalation_reason `security_review` and the registered sink
