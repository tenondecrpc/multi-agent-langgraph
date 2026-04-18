## ADDED Requirements

### Requirement: Two First-Class Helm Profiles

The repository SHALL maintain two first-class Helm profiles: `connected` and `air_gapped`. CI SHALL validate both profiles on every change touching `helm/`, backend config, or the persistence backbone.

#### Scenario: PR touching Helm validates both profiles
- **WHEN** a PR changes Helm values or backend config
- **THEN** CI renders both profiles and runs dry-run plus the air-gapped smoke
- **AND** any rendering or smoke failure blocks the merge
