## Why

The constitution mandates public status communication and incident runbooks. PLAN.md specifies a Prometheus-derived per-component status endpoint, a `status-page-sync` CronJob publishing health, public statuspage embed, SEV model with PagerDuty rotation, and a runbook per paging alert (including `all-providers-down.md` and `air-gapped-deployment.md`). Phase 7 set the direction; this change delivers the status surface and runbook corpus.

## What Changes

- Add `/api/v1/status-page` endpoint summarising per-component state derived from Prometheus queries; endpoint is read-only and public (air-gapped profile serves an internal equivalent).
- Add `status-page-sync` CronJob publishing to a statuspage-compatible consumer.
- Introduce a SEV1/2/3 severity model with PagerDuty on-call rotation wiring and an escalation matrix.
- Author a runbook for every paging Alertmanager rule; mandatory runbooks include `all-providers-down.md` and `air-gapped-deployment.md`.
- Link every alert to its runbook; CI lint fails when an alert is missing a runbook link.

## Capabilities

### New Capabilities

- `public-status-and-incident-response`: status endpoint, sync CronJob, SEV model, PagerDuty wiring, alert-to-runbook linking and lint.

### Modified Capabilities

- `observability-and-incident-response`: runbook corpus and alert-to-runbook lint become part of the observability surface.

## Impact

- Code: new FastAPI route, `status-page-sync` CronJob, alert YAML.
- Docs: `docs/runbooks/` corpus.
- Secrets: statuspage provider webhook or internal endpoint via External Secrets Operator.
- Deployment: air-gapped profile serves the status internally and omits the external sync.
- Constitution alignment: Tier 1 preserved.
