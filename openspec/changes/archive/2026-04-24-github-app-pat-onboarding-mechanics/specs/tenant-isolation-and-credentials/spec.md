## ADDED Requirements

### Requirement: GitHub Credentials Flow Through The Onboarding Record

Tenant GitHub credentials (App installation references and opt-in PAT ciphertext) SHALL be stored only through the integration onboarding record. Environment-variable or config-file storage of GitHub credentials is forbidden.

#### Scenario: Direct env-var usage is rejected
- **WHEN** code attempts to read a GitHub token from an environment variable or config file at runtime
- **THEN** a lint rule or startup check fails the build or the pod startup
- **AND** the operator sees a structured error referencing the onboarding surface
