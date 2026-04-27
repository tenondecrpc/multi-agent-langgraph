## ADDED Requirements

### Requirement: Promotion Gates Block Unsigned Or Unattested Images

A canary stage SHALL advance only when the image digest has a valid cosign signature and an SLSA Level 3 provenance attestation. Admission policy enforcement SHALL be the final authority; the rollout pipeline SHALL NOT bypass it.

#### Scenario: Unsigned image cannot promote
- **WHEN** an unsigned image enters the canary
- **THEN** the rollout aborts at the first analysis step
- **AND** the abort is recorded with the missing-attestation reason

### Requirement: Rollback Is Automated On SLO Burn

The rollout analysis SHALL consume the existing burn-rate signals for latency, error, and saturation. Crossing the abort threshold SHALL trigger an automated rollback to the stable revision.

#### Scenario: Burn-rate breach aborts canary
- **WHEN** the analysis window observes burn-rate above the abort threshold
- **THEN** all canary traffic is shifted back to the stable revision within the configured window
- **AND** an alert fires with the canary name, abort reason, and a link to the analysis run

### Requirement: Stuck Rollout Has A Break-Glass Recovery Path

If a rollout becomes stuck (paused beyond the maximum dwell window without progress), an operator SHALL be able to abort it via a documented break-glass procedure that requires audit logging.

#### Scenario: Manual abort writes audit
- **WHEN** an operator aborts a stuck rollout via break-glass
- **THEN** the action records actor, rationale, and timestamp
- **AND** the operator UI surfaces the audit trail
