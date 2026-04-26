## ADDED Requirements

### Requirement: Air-Gapped Routing Uses Only Internal Endpoints

Provider routing in the air-gapped profile SHALL consult only internal endpoints configured via Helm values. Fail-closed behavior SHALL apply when internal endpoints are unhealthy.

#### Scenario: Internal endpoint unhealthy is fail-closed
- **WHEN** the OpenCode Go endpoint is unhealthy in air-gapped mode
- **THEN** ticket routing fails closed
- **AND** the admin UI surfaces the outage with a runbook link
