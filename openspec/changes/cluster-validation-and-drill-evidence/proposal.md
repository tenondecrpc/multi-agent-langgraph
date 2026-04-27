## Why

`STATUS.md` is consistently honest that several Tier 1 controls are documented but not exercised: the ephemeral K3s integration test for admission policies, the air-gapped bundle verification, multi-replica load testing, mid-traffic rotation chaos, the KEK rotation drill and `rotate_kek.sh` script, the GDPR erasure drill, the RTO evidence bundle, and the paging drill. The result is a system that claims production readiness without published evidence.

This change defines the validation evidence program: which drills exist, how often they run, where evidence is stored, and how an operator proves to an auditor that a Tier 1 control was exercised end to end.

## What Changes

- Define the drill catalog: ephemeral K3s admission integration, air-gapped bundle verification, KEK rotation, mid-traffic webhook secret rotation, GDPR tenant erasure, DR backup and restore, paging escalation, all-providers-down failover, and progressive-delivery rollback.
- Define the cadence: which drills run on each commit, weekly, monthly, quarterly.
- Define the evidence contract: every drill writes a structured artifact (run identifier, profile, inputs, observed metrics, screenshots when applicable, signed timestamp) under `docs/drills/evidence/<drill>/<run-id>/`.
- Define the coverage matrix: which Tier 1 control is exercised by which drill, with no Tier 1 control left uncovered.
- Define the dual-control approval for destructive drills (KEK retirement, tenant erasure).
- Define the failure escalation: a failed drill opens a SEV2 internal incident automatically.
- Specify the air-gapped variant of each drill so the evidence bundle is reproducible without vendor egress.

## Capabilities

### Modified Capabilities

- `disaster-recovery-and-high-availability`: introduce the structured drill evidence program and DR runbook execution evidence requirements.
- `admission-control-and-attestation`: require the ephemeral K3s integration test to run on a defined cadence with archived evidence before the policy can advance from `Audit` to `Enforce`.
- `data-retention-and-compliance-operations`: tenant erasure quarterly drill becomes mandatory with archived evidence.

## Tier Classification

Tier 1. Operational drills are required by the constitution; this change makes their execution and evidence non-optional.

## Non-Goals

- Customer-production drills. All drills run in dedicated staging or ephemeral environments.
- A new evidence database; reuse PostgreSQL audit tables and a `docs/drills/evidence/` tree.
- A new alerting backend; reuse Prometheus and existing PagerDuty routing.
- Replacing existing runbooks; this change references and binds them.

## Operational Impact

- Operators commit time on a quarterly cadence to execute the destructive drills.
- Cluster cost increases for the ephemeral K3s integration job.
- The admission `Audit` to `Enforce` flip becomes contingent on archived evidence, which is a blocker for the existing supply-chain change archive task.

## Risk

- Drill execution can disrupt staging traffic; staging schedule must respect maintenance windows.
- Stale evidence (older than the documented validity window) must be treated as missing; auditors must not accept expired evidence.
- A drill that always passes by accident is worse than no drill; each drill must include a deliberate-failure variant.

## Rollback / Degradation

- A drill that fails escalates rather than rolling back; the system already deploys safely under failure.
- The `Audit` to `Enforce` flip is the only externally visible degradation gate; until evidence is fresh, admission stays in `Audit`.
- Tenant erasure drills run on a synthesized tenant, never on a real customer tenant.
