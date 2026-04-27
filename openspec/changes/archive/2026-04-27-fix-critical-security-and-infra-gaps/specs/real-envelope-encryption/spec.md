## ADDED Requirements

### Requirement: AES-256-GCM envelope encryption
The system SHALL use AES-256-GCM for envelope encryption of all credentials, secrets, and sensitive payloads stored in PostgreSQL. The `EnvelopeCipher` class SHALL produce ciphertext that is cryptographically secure and not recoverable without the wrapping key.

#### Scenario: Encrypt produces real ciphertext
- **WHEN** `EnvelopeCipher.encrypt(plaintext)` is called with a non-empty string
- **THEN** the returned ciphertext is NOT base64-decodable to the original plaintext
- **AND** the ciphertext can only be decrypted with the correct wrapping key via `EnvelopeCipher.decrypt(ciphertext)`

#### Scenario: Decrypt recovers original plaintext
- **WHEN** `EnvelopeCipher.encrypt(plaintext)` produces ciphertext and `EnvelopeCipher.decrypt(ciphertext)` is called
- **THEN** the returned value equals the original plaintext

#### Scenario: Different plaintexts produce different ciphertexts
- **WHEN** two different plaintexts are encrypted with the same key
- **THEN** the resulting ciphertexts are different

#### Scenario: Random nonce ensures uniqueness
- **WHEN** the same plaintext is encrypted twice with the same key
- **THEN** the resulting ciphertexts are different due to random nonce generation

### Requirement: Key rotation support
The system SHALL support key rotation with an active key and multiple previous keys. Decryption SHALL succeed with any valid key in the rotation set.

#### Scenario: Decrypt with previous key
- **WHEN** data was encrypted with a previous key that is still in the rotation set
- **AND** `EnvelopeCipher.decrypt(ciphertext)` is called
- **THEN** decryption succeeds and returns the original plaintext

#### Scenario: Decrypt fails with unknown key ID
- **WHEN** ciphertext references a key ID not in the active or previous keys set
- **AND** `EnvelopeCipher.decrypt(ciphertext)` is called
- **THEN** decryption raises a `ValueError`

### Requirement: Cryptography dependency
The system SHALL use the `cryptography` library (Fernet or AES-GCM primitives) for encryption operations. The `cryptography` package SHALL be listed in `pyproject.toml` dependencies.

#### Scenario: Cryptography package is available
- **WHEN** the backend dependencies are installed via `uv sync`
- **THEN** `import cryptography` succeeds without error
