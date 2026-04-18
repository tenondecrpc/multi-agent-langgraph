## ADDED Requirements

### Requirement: Only Signed And Attested Images Are Promotable

Progressive delivery stages SHALL reject images that are unsigned or lack SLSA Level 3 provenance. This invariant SHALL hold in both connected and `air_gapped` profiles.

#### Scenario: Promotion blocked on missing attestation
- **WHEN** a candidate image lacks provenance
- **THEN** the promotion step refuses to proceed
- **AND** the release pipeline surfaces the failure with a runbook link
