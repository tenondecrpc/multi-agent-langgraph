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
| Weighted-fair queue load                     | monthly    | staging         | no          | no           |
| Sandbox egress and gVisor                    | monthly    | ephemeral       | no          | no           |
| API diff and version gate                    | monthly    | CI fixture      | no          | no           |
| DLQ and graceful shutdown                    | monthly    | staging         | no          | no           |
| KEK rotation                                 | quarterly  | staging         | yes         | yes          |
| DR backup and restore                        | quarterly  | staging         | yes         | yes          |
| GDPR tenant erasure                          | quarterly  | staging         | yes         | yes          |

Each drill maps to one or more Tier 1 controls. The mapping lives in `docs/drills/coverage-matrix.md`.

The catalog reinforces existing runbooks rather than replacing them. Each entry SHALL name its owner runbook, Tier 1 control coverage, deliberate-failure variant, profile target, and freshness window. Destructive drills run only on synthesized tenants and require dual-control before execution starts.

## Evidence Contract

Each drill run writes a structured artifact:

```
docs/drills/evidence/<drill>/<run-id>/
  metadata.json     # actor, profile, start/end, signed timestamp
  inputs.json       # parameters, fixture identifiers
  observations.md   # operator narrative
  metrics.csv       # exported Prometheus samples
  manifest.sig      # signature over canonical evidence manifest
  screenshots/      # optional
  status.json       # pass/fail, escalations triggered
```

A signed timestamp prevents post-hoc edits. The `metadata.json` file includes a hash of the run.

The signed timestamp is computed from a canonical manifest of all evidence files except `manifest.sig`. Connected environments MAY use keyless signing with GitHub Actions OIDC. `air_gapped` environments SHALL use the configured internal signing root or offline operator key. Freshness is based on the signed `finished_at` timestamp, not file modification time.

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

The manifest includes policy name, policy revision, source and target mode, target profile, target cluster, evidence hashes, approvers, workflow run URL, signature reference, and rollback mode. If consulted evidence is later invalidated, the system opens a SEV2 incident, blocks further flips, and rolls non-production policies back to `Audit`.

## Deliberate-Failure Variants

Each drill SHALL include a deliberate-failure variant to prove the drill detects regressions:

- Admission drill: deploy an unsigned image and assert rejection.
- Failover drill: kill the active provider connection and assert escalation.
- Rotation drill: present an expired secret and assert webhook rejection.
- Erasure drill: omit a cascade table and assert detection.
- Air-gapped bundle drill: remove a mirrored trust root or bundle manifest entry and assert verification failure.
- Progressive delivery drill: inject a failed canary metric and assert rollback.
- Queue drill: overload one tenant queue and assert other tenants retain scheduled throughput.
- Sandbox drill: attempt forbidden egress or privileged execution and assert denial.
- API diff drill: introduce a breaking OpenAPI diff and assert gate failure.
- DLQ drill: force worker shutdown mid-run and assert checkpoint-boundary stop plus DLQ routing.
- DR drill: corrupt or omit a backup artifact and assert restore validation failure.

## Observability

- Metrics: `devsquad_drill_runs_total{drill,result}`, `devsquad_drill_evidence_age_days{drill}`.
- Alerts: drill failure, drill evidence expired, admission flip attempted with stale evidence.
- Dashboards: drill calendar and freshness map.

Additional metrics are `devsquad_drill_evidence_expired_total{drill,profile}`, `devsquad_drill_deliberate_failure_detections_total{drill,result}`, `devsquad_drill_incidents_total{drill,severity}`, and `devsquad_admission_flip_gate_denials_total{reason}`. Dashboards SHALL include a Tier 1 coverage heatmap and incident status panel. Drill failure, expired evidence, failed deliberate-failure detection, or stale-evidence admission flip attempts open or update a SEV2 internal incident.

## Protected Workflow Invariants

- Drills SHALL exercise the existing escalation sinks; they do not invent new ones.
- Destructive drills SHALL run on synthesized tenants in staging, never on real customer tenants.
- The change introduces no repo-writing surface.
- Both connected and `air_gapped` profiles are addressed in the catalog.
- Missing or expired evidence never weakens Tier 1 controls; it blocks gated actions or escalates.
