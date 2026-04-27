## 1. Artifact Alignment

- [x] 1.1 Confirm scope reinforces existing operational runbooks rather than duplicating them.
- [x] 1.2 Reconcile the drill catalog with the constitution Tier 1 list.

## 2. Drill Catalog

- [x] 2.1 Enumerate drills, cadence, profile, destructiveness, and dual-control flag.
- [x] 2.2 Map each drill to the Tier 1 controls it exercises.
- [x] 2.3 Specify the deliberate-failure variant per drill.

## 3. Evidence Contract

- [x] 3.1 Specify the directory layout and file contracts.
- [x] 3.2 Specify the signed-timestamp mechanism.
- [x] 3.3 Specify the validity windows per cadence.

## 4. Admission Flip Gate

- [x] 4.1 Specify the admission `Audit` to `Enforce` evidence requirements.
- [x] 4.2 Specify the signed manifest produced on flip.
- [x] 4.3 Specify the rollback path if evidence is later invalidated.

## 5. Observability

- [x] 5.1 Enumerate metrics, alerts, and dashboards.
- [x] 5.2 Specify a SEV2 internal incident on drill failure.

## 6. Verification (Specification Phase)

- [x] 6.1 Confirm Tier 1 controls are covered by at least one drill.
- [x] 6.2 Confirm both deployment profiles are addressed.
- [x] 6.3 Confirm destructive drills require dual-control and run on synthesized tenants.

## 7. Implementation (Deferred)

- [x] 7.1 Implementation of drill scripts, ephemeral K3s harness, evidence tooling, and admission flip script is deferred to a follow-up apply.
