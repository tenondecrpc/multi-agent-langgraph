# Incident Severity And Paging

## Severity Model

### SEV1

Customer-visible outage, data-integrity risk, tenant isolation failure, or a security control failure with active exposure.

Response target: page primary immediately, escalate to secondary after 10 minutes without acknowledgement, and assign an incident commander.

### SEV2

Material degradation without full outage, repeated SLO burn-rate breach, provider failover exhaustion, or blocked PR creation across multiple tenants.

Response target: page primary during business hours and on-call after-hours, escalate after 20 minutes without acknowledgement.

### SEV3

Single-component issue with a documented workaround, non-page warning alert, or isolated tenant impact without data-integrity risk.

Response target: ticket to the owning team, review during the next operational handoff, and promote to SEV2 if impact expands.

## Escalation Matrix

| Severity | Primary owner | Secondary owner | Communications |
| --- | --- | --- | --- |
| SEV1 | On-call incident commander | Platform lead | Public status update within 15 minutes |
| SEV2 | Service owner on call | Incident commander | Status update if customer-visible beyond 30 minutes |
| SEV3 | Component owner | Platform triage | Internal note only unless impact expands |

## Paging Rules

- Every Alertmanager rule with `severity: page` must include a runbook reference.
- PagerDuty service ownership is mapped by alert `subsystem`.
- Security, tenant-boundary, and data-integrity alerts always page, even if the current blast radius is unclear.
- Air-gapped deployments use the customer-owned paging bridge; no vendor-operated control plane is required.
