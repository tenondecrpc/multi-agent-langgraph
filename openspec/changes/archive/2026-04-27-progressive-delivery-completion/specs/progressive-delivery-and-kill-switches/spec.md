## ADDED Requirements

### Requirement: High-Risk Capabilities Are Governed By Kill Switches

The system SHALL expose an OpenFeature-backed kill switch for every high-risk runtime capability listed in the design table: provider routing override, LLM provider enablement, sandbox enforcement, internal RAG, webhook acceptance, PR creation, graph activation, ticket processing, and admission enforce mode. Each kill switch SHALL have a default state, a documented failure mode when the flag service is unreachable, a rollback path, and an audit trail.

#### Scenario: Default fail-closed for sandbox enforcement
- **WHEN** the flag service is unreachable past the local cache TTL
- **THEN** sandbox enforcement remains on
- **AND** the pod records a degraded readiness reason

#### Scenario: PR creation kill switch pauses before repo write completion
- **WHEN** `pr_creation` is denied during a run
- **THEN** the runtime pauses at the pre-PR escalation boundary
- **AND** it records the registered escalation reason without bypassing test, review, diff guard, or pre-PR sync requirements

#### Scenario: Admission enforce mode never relaxes after activation
- **WHEN** `ops.admission_enforce_mode` has been activated and the flag service becomes unreachable
- **THEN** admission enforcement remains at the last-known-good enforce state
- **AND** the system does not silently fall back to Audit mode

#### Scenario: Audit trail on every flip
- **WHEN** an operator flips a kill switch
- **THEN** the system writes an audit row with actor, before, after, justification, and shadow-mode result
- **AND** the audit row is queryable by tenant-admin and super-admin roles

### Requirement: Kill-Switch Propagation Is Bounded

A flag flip on a high-risk capability SHALL propagate to 99% of running backend, worker, and frontend pods within 60 seconds and to 100% of pods within 120 seconds, observable through `devsquad_kill_switch_propagation_seconds`. Breaching either SLO SHALL fire an alert.

#### Scenario: Propagation breach fires alert
- **WHEN** a kill-switch flip is not observed by all pods within the SLO window
- **THEN** an alert fires with the affected capability, replica count, and observed median propagation
- **AND** the alert label points to a checked-in runbook

#### Scenario: Operator UI shows propagation state
- **WHEN** an operator opens the kill-switch view
- **THEN** the UI shows current state, source version, stale status, last actor, last justification, and observed pod count
- **AND** it does not expose SDK keys, provider credentials, or secret values

#### Scenario: Stuck flag requires dual super-admin recovery
- **WHEN** a fail-closed flag is stuck in a state that cannot be reconciled by normal propagation
- **THEN** force-clear requires two super-admin approvals, a justification, and an `ops://release` record
- **AND** the audit row links the before state, after state, approvers, and rollback version

### Requirement: Flag State Lives In Versioned PostgreSQL Config

The flag state SHALL live in the same versioned PostgreSQL control-plane that owns the runtime graph configuration. The system SHALL NOT introduce a separate datastore for flag state. State SHALL be represented by `feature_flag_states` and `feature_flag_state_versions` records.

#### Scenario: Feature flag state schema supports rollback
- **WHEN** a flag state is persisted
- **THEN** `feature_flag_states` records tenant, team, flag key, capability, current state, default state, fail-closed marker, version, owner, last actor, last justification, and timestamps
- **AND** `feature_flag_state_versions` records before state, after state, actor, approver actor when required, justification, shadow result, source, creation time, and rollback-of-version when applicable

#### Scenario: Shadow-mode validation before activation
- **WHEN** a flag flip is submitted for a fail-closed capability
- **THEN** the system runs the candidate state in shadow mode for the configured window
- **AND** the activation is denied if the shadow-mode result reports policy regressions

#### Scenario: High-risk activation uses a validation window
- **WHEN** an operator enables or relaxes a high-risk capability
- **THEN** the candidate state runs through a 10 minute shadow-mode validation window
- **AND** activation is blocked when repo-write gates, sandbox enforcement, provider routing, or policy-mode checks regress

### Requirement: Air-Gapped Profile Stays Functional Without Vendor Flag SaaS

The `air_gapped` profile SHALL bundle a local flag service. The system SHALL NOT depend on any vendor-hosted flag SaaS in the air-gapped profile.

#### Scenario: Air-gapped boot with reachable local flag service
- **WHEN** the cluster runs in `air_gapped` profile and the local flag service is reachable
- **THEN** pods evaluate flags normally and refresh the on-disk last-known-good cache
- **AND** the flag state is read from the local PostgreSQL-backed control plane

#### Scenario: Air-gapped boot with unreachable local flag service
- **WHEN** the local flag service is unreachable past the local cache TTL
- **THEN** pods continue to serve cached flag state for fail-closed capabilities only
- **AND** any new high-risk capability activation request is denied

#### Scenario: Last-known-good cache is bounded
- **WHEN** a pod writes a local flag cache
- **THEN** it writes to `/var/run/devsquad/feature-flags/cache.json` on tmpfs with a signed state version and TTL
- **AND** the cache is evicted on version supersession, signature mismatch, tenant scope mismatch, or pod restart

### Requirement: Kill-Switch Drills Produce Evidence

The operations program SHALL run a quarterly kill-switch drill that flips one governed capability in staging, observes propagation, restores the prior state, and files evidence.

#### Scenario: Quarterly drill records propagation evidence
- **WHEN** the quarterly kill-switch drill runs
- **THEN** the evidence includes the flag version, pod observations, propagation metrics, audit rows, restore action, and operator UI screenshot or API output
- **AND** any propagation SLO breach opens a follow-up item through `ops://release`
