## ADDED Requirements

### Requirement: Promotion Gates Block Unsigned Or Unattested Images

A canary stage SHALL advance only when the image digest has a valid cosign signature and an SLSA Level 3 provenance attestation. Admission policy enforcement SHALL be the final authority; the rollout pipeline SHALL NOT bypass it. The promotion gate matrix SHALL also require healthy SLO analysis, no active SEV1 or SEV2 incident for the affected service, and no denied or stale high-risk kill switch required by the rollout.

#### Scenario: Unsigned image cannot promote
- **WHEN** an unsigned image enters the canary
- **THEN** the rollout aborts at the first analysis step
- **AND** the abort is recorded with the missing-attestation reason

#### Scenario: Active incident blocks promotion
- **WHEN** a candidate rollout targets a service with an active SEV1 or SEV2 incident
- **THEN** the promotion gate pauses or aborts the rollout before the next traffic increase
- **AND** the release evidence links the incident id and hold reason

#### Scenario: Denied kill switch blocks promotion
- **WHEN** a capability required by the candidate rollout has a denied or stale high-risk kill switch
- **THEN** the rollout does not advance
- **AND** the evidence records the flag key, version, and kill-switch state

### Requirement: Rollback Is Automated On SLO Burn

The rollout analysis SHALL consume the existing burn-rate signals for latency, error, saturation, circuit-breaker opens, DLQ growth, pool saturation, worker retry growth, and checkpoint lag. Crossing the abort threshold SHALL trigger an automated rollback to the stable revision.

#### Scenario: Backend canary uses staged weights
- **WHEN** the backend API rollout starts
- **THEN** traffic advances through 5%, 25%, 50%, and 100% stages
- **AND** the 5%, 25%, and 50% stages each pause for analysis before promotion

#### Scenario: Worker canary uses bounded cohorts
- **WHEN** the worker rollout starts
- **THEN** work advances through 5%, 25%, 50%, and 100% worker replica or queue-shard cohorts
- **AND** each analysis checks job failure rate, retry growth, checkpoint lag, DLQ growth, and pool saturation

#### Scenario: Frontend blue-green requires smoke before promote
- **WHEN** a frontend candidate is deployed to the preview service
- **THEN** smoke, API compatibility, asset integrity, and client-error checks must pass
- **AND** the active service is not promoted until the gate succeeds

#### Scenario: Burn-rate breach aborts canary
- **WHEN** the analysis window observes burn-rate above the abort threshold
- **THEN** all canary traffic is shifted back to the stable revision within the configured window
- **AND** an alert fires with the canary name, abort reason, and a link to the analysis run
- **AND** the rollback completes within 2 minutes of the failed analysis result

### Requirement: Stuck Rollout Has A Break-Glass Recovery Path

If a rollout becomes stuck (paused beyond the maximum dwell window without progress), an operator SHALL be able to abort it via a documented break-glass procedure that requires audit logging.

#### Scenario: Manual abort writes audit
- **WHEN** an operator aborts a stuck rollout via break-glass
- **THEN** the action records actor, rationale, and timestamp
- **AND** the operator UI surfaces the audit trail

#### Scenario: Manual abort records release evidence
- **WHEN** a stuck rollout is manually aborted
- **THEN** the audit record includes rollout name, stable revision, candidate revision, analysis link, actor, rationale, timestamp, and escalation sink `ops://release`
- **AND** human approval remains limited to the stuck-rollout exception path

### Requirement: Rollout Abort Drills Validate Automation

The release program SHALL run a quarterly rollout-abort drill in staging by deliberately failing an analysis check and proving that the rollout automatically returns to the stable revision.

#### Scenario: Rollout-abort drill files evidence
- **WHEN** the quarterly rollout-abort drill runs
- **THEN** the evidence includes rollout id, abort reason, stable revision, candidate revision, analysis run, Alertmanager event, and rollback duration
- **AND** failed drill evidence opens a release-engineering follow-up item
