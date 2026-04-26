## ADDED Requirements

### Requirement: Public Status Endpoint Derives From Prometheus Without Customer Data

The backend SHALL expose `/api/v1/status-page` returning a whitelist-only summary per component with one of `operational`, `degraded`, `partial_outage`, `major_outage`. The response SHALL NOT include customer identifiers, tenant identifiers, ticket contents, or sensitive metadata.

#### Scenario: Public response contains only whitelisted fields
- **WHEN** a client calls the endpoint
- **THEN** the response schema matches the documented whitelist
- **AND** any attempted leak of non-whitelisted fields fails CI contract tests

### Requirement: Status Page Sync Job Publishes Externally In Connected Mode Only

A `status-page-sync` CronJob SHALL publish the summary to the statuspage endpoint in the connected profile. In `air_gapped`, the CronJob SHALL be disabled and the admin UI SHALL read directly.

#### Scenario: Air-gapped profile does not attempt external sync
- **WHEN** the deployment is `air_gapped`
- **THEN** no outbound call to an external statuspage endpoint occurs
- **AND** the internal admin UI surfaces the same data

### Requirement: Severity Model And On-Call Rotation

SEV1, SEV2, SEV3 SHALL be formally defined with PagerDuty integration. Every paging alert SHALL map to a severity and an on-call rotation.

#### Scenario: SEV1 pages primary and secondary
- **WHEN** a SEV1 alert fires
- **THEN** PagerDuty pages the primary on-call and escalates to secondary on no-ack within the policy window

### Requirement: Every Paging Alert Has A Runbook

Every Alertmanager rule with paging severity SHALL carry a `runbook_url` label pointing to an existing file under `docs/runbooks/`. CI lint SHALL block merges that violate this rule. Mandatory runbooks include `all-providers-down.md` and `air-gapped-deployment.md`.

#### Scenario: Missing runbook fails CI
- **WHEN** a PR adds a paging alert without a runbook link
- **THEN** CI lint fails with an actionable error
