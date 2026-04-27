## ADDED Requirements

### Requirement: High-Risk Capabilities Are Governed By Kill Switches

The system SHALL expose an OpenFeature-backed kill switch for every high-risk runtime capability listed in the design table. Each kill switch SHALL have a default state, a documented failure mode when the flag service is unreachable, and an audit trail.

#### Scenario: Default fail-closed for sandbox enforcement
- **WHEN** the flag service is unreachable past the local cache TTL
- **THEN** sandbox enforcement remains on
- **AND** the pod records a degraded readiness reason

#### Scenario: Audit trail on every flip
- **WHEN** an operator flips a kill switch
- **THEN** the system writes an audit row with actor, before, after, justification, and shadow-mode result
- **AND** the audit row is queryable by tenant-admin and super-admin roles

### Requirement: Kill-Switch Propagation Is Bounded

A flag flip on a high-risk capability SHALL propagate to all running pods within a configured propagation SLO, observable through `devsquad_kill_switch_propagation_seconds`. Breaching the SLO SHALL fire an alert.

#### Scenario: Propagation breach fires alert
- **WHEN** a kill-switch flip is not observed by all pods within the SLO window
- **THEN** an alert fires with the affected capability, replica count, and observed median propagation
- **AND** the alert label points to a checked-in runbook

### Requirement: Flag State Lives In Versioned PostgreSQL Config

The flag state SHALL live in the same versioned PostgreSQL control-plane that owns the runtime graph configuration. The system SHALL NOT introduce a separate datastore for flag state.

#### Scenario: Shadow-mode validation before activation
- **WHEN** a flag flip is submitted for a fail-closed capability
- **THEN** the system runs the candidate state in shadow mode for the configured window
- **AND** the activation is denied if the shadow-mode result reports policy regressions

### Requirement: Air-Gapped Profile Stays Functional Without Vendor Flag SaaS

The `air_gapped` profile SHALL bundle a local flag service. The system SHALL NOT depend on any vendor-hosted flag SaaS in the air-gapped profile.

#### Scenario: Air-gapped boot with reachable local flag service
- **WHEN** the cluster runs in `air_gapped` profile and the local flag service is reachable
- **THEN** pods evaluate flags normally and refresh the on-disk last-known-good cache

#### Scenario: Air-gapped boot with unreachable local flag service
- **WHEN** the local flag service is unreachable past the local cache TTL
- **THEN** pods continue to serve cached flag state for fail-closed capabilities only
- **AND** any new high-risk capability activation request is denied
