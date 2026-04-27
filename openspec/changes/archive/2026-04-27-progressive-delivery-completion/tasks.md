## 1. Artifact Alignment

- [x] 1.1 Confirm scope does not duplicate the archived progressive-delivery scaffolding; this change finishes it.
- [x] 1.2 Reconcile the kill-switch capability table with `release-engineering-and-feature-flags` and `progressive-delivery-and-kill-switches` specs.

## 2. Rollout Pipeline Specification

- [x] 2.1 Define backend, worker, and frontend canary stages, traffic weights, and pause windows.
- [x] 2.2 Define analysis template inputs from the existing burn-rate metrics; specify abort thresholds.
- [x] 2.3 Define rollback contract: automatic on abort, manual on stuck rollout, audit row required.
- [x] 2.4 Define promotion gate matrix (signature + provenance + SLO + incident state + kill switch).

## 3. Kill-Switch Contract

- [x] 3.1 Enumerate Tier 1 capabilities under kill-switch governance (table in `design.md`).
- [x] 3.2 Define the propagation SLO from flag flip to pod observation.
- [x] 3.3 Define the operator UI surface (read-only state, dual-control flip for fail-closed flags).
- [x] 3.4 Define stuck-flag recovery procedure with dual super-admin approval.

## 4. Air-Gapped Profile

- [x] 4.1 Specify local flag-service deployment for `air_gapped` Helm profile.
- [x] 4.2 Specify last-known-good cache contract: TTL, path, eviction, reset.
- [x] 4.3 Specify behavior when the flag service is unreachable past TTL: deny new high-risk activations, never relax existing fail-closed defaults.

## 5. Persistence And Shadow Mode

- [x] 5.1 Specify `feature_flag_states` and `feature_flag_state_versions` schemas (no new datastore; reuse PostgreSQL control-plane).
- [x] 5.2 Specify shadow-mode validation window for high-risk flags.
- [x] 5.3 Specify audit trail fields: actor, before, after, justification, shadow result.

## 6. Observability And Drills

- [x] 6.1 Define metrics, alerts, dashboards listed in `design.md`.
- [x] 6.2 Define quarterly kill-switch drill: pick one capability, flip it, observe propagation, restore, file evidence.
- [x] 6.3 Define rollout-abort drill: deliberately fail an analysis check in staging.

## 7. Verification (Specification Phase)

- [x] 7.1 Confirm the specification preserves Tier 1 invariants (signed-and-attested images, break-glass-only human approval, no new datastore).
- [x] 7.2 Confirm both deployment profiles are addressed.
- [x] 7.3 Confirm rollback path exists for every newly governed capability.

## 8. Implementation (Deferred)

- [x] 8.1 Implementation of CI, Helm, backend, frontend, runbook, and drill artifacts is out of scope for this SDD-only change and will be scheduled in a follow-up apply.
