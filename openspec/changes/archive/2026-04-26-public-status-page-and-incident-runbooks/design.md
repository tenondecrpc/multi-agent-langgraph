# Design: Public Status Page And Incident Runbooks

## Context

Phase 7 established observability and incident response; this change adds the public-facing status surface and the runbook corpus that the alerting pipeline needs.

## Goals / Non-Goals

### Goals

- Read-only public status endpoint derived from Prometheus.
- Automated sync to a statuspage consumer.
- Paging integration with a documented severity model.
- A runbook for every paging alert, linted in CI.

### Non-Goals

- No public-facing ticket content or tenant metadata in the status page.
- No custom-built status provider; adopt one statuspage-compatible format.

## Decisions

### Decision: `/api/v1/status-page` derives from Prometheus

The endpoint runs a fixed set of Prometheus queries per component (API, workers, DB, Redis, provider routing, sandbox runtime, persistence backbone) and returns a compact summary per component with `operational | degraded | partial_outage | major_outage`. No customer-identifiable data appears.

### Decision: `status-page-sync` CronJob

A CronJob posts the summary to the customer-configured statuspage endpoint. In air-gapped profile, the CronJob is disabled and the internal admin UI reads the endpoint directly.

### Decision: SEV model and paging

SEV1: customer-visible outage or data-integrity risk. SEV2: degraded behavior, SLO breach without full outage. SEV3: single-component issue with workaround. PagerDuty service IDs per severity; escalation matrix documented.

### Decision: Alert-to-runbook lint

A CI step parses Alertmanager rules and verifies every paging alert has a `runbook_url` label pointing to an existing file under `docs/runbooks/`.

## Risks / Trade-offs

- Drift between alerts and runbooks. Mitigated by CI lint.
- Status-page leakage. Mitigated by whitelist-only summary schema and staging smoke.

## Migration Plan

1. Ship `/api/v1/status-page` endpoint and internal admin-UI tile.
2. Add CronJob wired to staging statuspage first.
3. Author runbooks for existing alerts; enable CI lint.
4. Enable PagerDuty rotation and test paging.
