## ADDED Requirements

### Requirement: Retention CronJobs Enforce Per-Surface Policies

Retention CronJobs SHALL drop `metering_facts` partitions outside retention, evict memory rows by TTL, delete checkpoints outside retention, and expire DLQ records per policy. Each run SHALL emit deletion counts per surface.

#### Scenario: Partition drop succeeds and is observable
- **WHEN** the retention CronJob runs for metering
- **THEN** the month partition older than policy is dropped
- **AND** a retention-run metric records the partition id and row count

#### Scenario: TTL evictions for memory are batched and bounded
- **WHEN** memory TTL eviction runs
- **THEN** the job processes rows in batches with bounded lock windows
- **AND** the job reports elapsed time and rows evicted

### Requirement: Tenant Delete Is Approved And Cascades Completely

Tenant delete SHALL require super_admin approval and SHALL cascade across configs, checkpoints, memory, metering, sessions, credentials, and sprites. Audit rows SHALL be pseudonymized rather than deleted.

#### Scenario: Unapproved tenant-delete request is refused
- **WHEN** a tenant-delete request is not approved
- **THEN** no deletion occurs
- **AND** the request remains visible for approval or rejection

#### Scenario: Cascade completion is auditable
- **WHEN** the cascade completes
- **THEN** per-table deletion counts are recorded on the `tenant_delete_events` row
- **AND** an audit event is emitted

### Requirement: DPA Acknowledgement Gate

Ticket processing SHALL be blocked per tenant until the customer super_admin has acknowledged the current DPA version. New DPA versions SHALL require re-acknowledgement within a configurable grace period.

#### Scenario: Unacknowledged DPA blocks processing
- **WHEN** a tenant has not acknowledged the current DPA version
- **THEN** webhook acceptance is refused with a typed compliance error
- **AND** the admin UI surfaces the outstanding acknowledgement

#### Scenario: DPA version change re-prompts
- **WHEN** a new DPA version is published
- **THEN** the tenant remains accepting under the previous version for a grace window
- **AND** after the grace window, processing is blocked until re-acknowledgement

### Requirement: GDPR Erasure Runbook With Defined RPO And RTO

The `docs/` operator guide SHALL contain a GDPR erasure runbook with defined RPO and RTO targets and audit-evidence requirements.

#### Scenario: Erasure request completes within RTO
- **WHEN** a GDPR erasure request is approved
- **THEN** the cascade completes within the documented RTO
- **AND** the evidence bundle is retained per policy
