## ADDED Requirements

### Requirement: Fail closed on missing encryption config
The system SHALL refuse to start when encryption wrapping keys are not configured. The `EnvelopeCipher` SHALL validate that `active_key_id` is not `"unset"` and that wrapping key environment variables are set before accepting encryption or decryption operations.

#### Scenario: Startup fails when wrapping key is unset
- **WHEN** `BACKEND_ENCRYPTION_ACTIVE_KEY_ID` is `"unset"` or not set
- **AND** the application attempts to initialize `EnvelopeCipher`
- **THEN** a `RuntimeError` is raised with a message indicating the missing configuration

#### Scenario: Startup fails when wrapping key material is missing
- **WHEN** `BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY` is not set
- **AND** the application attempts to initialize `EnvelopeCipher`
- **THEN** a `RuntimeError` is raised with a message indicating the missing configuration

### Requirement: Fail closed on missing webhook secret
The system SHALL refuse to process webhooks when the shared secret is not configured. The webhook guard SHALL validate that the secret is not the development default before accepting any webhook verification requests.

#### Scenario: Webhook guard rejects when secret is default
- **WHEN** the webhook shared secret equals `"development-shared-secret"`
- **AND** a webhook verification request is received
- **THEN** the guard raises a `RuntimeError` and rejects the request

#### Scenario: Webhook guard rejects when secret is empty
- **WHEN** the webhook shared secret is empty or not set
- **AND** a webhook verification request is received
- **THEN** the guard raises a `RuntimeError` and rejects the request

### Requirement: No hardcoded default secrets
No module SHALL define a default value for secrets, wrapping keys, or webhook secrets that is a known string. All secret defaults SHALL be `None` or raise an error on use.

#### Scenario: No development defaults in production code
- **WHEN** the codebase is scanned for hardcoded secret strings
- **THEN** no file contains `"development-shared-secret"`, `"development-wrapping-key"`, or similar known defaults
