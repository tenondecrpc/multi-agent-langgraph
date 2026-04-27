## Architecture Reuse

- Reuse the existing runbooks under `docs/runbooks/` and the existing `docs/drills/` directory.
- Reuse PostgreSQL audit tables; add a `drill_runs` table only if no existing audit table fits.
- Reuse Prometheus metrics and the existing alert routing.
- Reuse the admission `Audit` and `Enforce` modes already specified in the supply-chain change.

## Drill Catalog

| Drill                                        | Cadence    | Profile target | Destructive | Dual-control |
|----------------------------------------------|------------|-----------------|-------------|--------------|
| Ephemeral K3s admission integration          | per commit | ephemeral       | no          | no           |
| Air-gapped bundle verification               | weekly     | air-gapped lab  | no          | no           |
| All-providers-down failover                  | weekly     | staging         | no          | no           |
| Mid-traffic webhook secret rotation          | monthly    | staging         | no          | no           |
| Progressive-delivery rollback drill          | monthly    | staging         | no          | no           |
| Paging escalation                            | monthly    | staging         | no          | no           |
| KEK rotation                                 | quarterly  | staging         | yes         | yes          |
| DR backup and restore                        | quarterly  | staging         | yes         | yes          |
| GDPR tenant erasure                          | quarterly  | staging         | yes         | yes          |

Each drill maps to one or more Tier 1 controls. The mapping lives in `docs/drills/coverage-matrix.md`.

## Evidence Contract

Each drill run writes a structured artifact:

```
docs/drills/evidence/<drill>/<run-id>/
  metadata.json     # actor, profile, start/end, signed timestamp
  inputs.json       # parameters, fixture identifiers
  observations.md   # operator narrative
  metrics.csv       # exported Prometheus samples
  screenshots/      # optional
  status.json       # pass/fail, escalations triggered
```

A signed timestamp prevents post-hoc edits. The `metadata.json` file includes a hash of the run.

## Validity Windows

| Drill                                | Validity window |
|--------------------------------------|------------------|
| Per-commit drills                    | until next commit |
| Weekly drills                        | 14 days           |
| Monthly drills                       | 60 days           |
| Quarterly drills                     | 120 days          |

Evidence older than its validity window is treated as missing.

## Admission Flip Gate

The admission `Audit` to `Enforce` flip SHALL be allowed only when:

- The ephemeral K3s admission integration evidence is fresh.
- The air-gapped bundle verification evidence is fresh.
- No SEV1 or SEV2 incident is open against the supply chain.

A signed manifest SHALL be produced when the flip is approved, recording the evidence hashes consulted.

## Deliberate-Failure Variants

Each drill SHALL include a deliberate-failure variant to prove the drill detects regressions:

- Admission drill: deploy an unsigned image and assert rejection.
- Failover drill: kill the active provider connection and assert escalation.
- Rotation drill: present an expired secret and assert webhook rejection.
- Erasure drill: omit a cascade table and assert detection.

## Observability

- Metrics: `devsquad_drill_runs_total{drill,result}`, `devsquad_drill_evidence_age_days{drill}`.
- Alerts: drill failure, drill evidence expired, admission flip attempted with stale evidence.
- Dashboards: drill calendar and freshness map.

## Protected Workflow Invariants

- Drills SHALL exercise the existing escalation sinks; they do not invent new ones.
- Destructive drills SHALL run on synthesized tenants in staging, never on real customer tenants.
- The change introduces no repo-writing surface.
