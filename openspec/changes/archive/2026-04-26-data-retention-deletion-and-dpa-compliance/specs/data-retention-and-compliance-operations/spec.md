## ADDED Requirements

### Requirement: Retention Jobs Are Observable And Alertable

Each retention job SHALL emit duration, rows-affected, and success metrics. Failed runs SHALL alert and SHALL not silently skip.

#### Scenario: Retention-job failure alerts
- **WHEN** a retention CronJob fails or times out
- **THEN** an alert fires for the owning team
- **AND** the runbook is linked in the alert payload
