## 1. Artifact Alignment

- [ ] 1.1 Confirm scope does not duplicate existing contract tests; this change adds the chaos, fuzz, and prompt regression layer.
- [ ] 1.2 Reconcile with `quality-engineering-strategy` to position the new suites in the canonical test ladder.

## 2. Chaos Catalog

- [ ] 2.1 Enumerate scenarios under `backend/tests/chaos/<area>/` with seed, fault model, and expected escalation reason.
- [ ] 2.2 Specify the deterministic-seed contract for fault injection.
- [ ] 2.3 Specify the recovery assertion: each scenario must observe escalation and verify recovery against the registered sink.

## 3. Fuzz Catalog

- [ ] 3.1 Enumerate fuzz targets and their input shapes.
- [ ] 3.2 Specify the corpus checked-in policy and crash shrinking process.
- [ ] 3.3 Specify the per-run time budget and failure artifact format.

## 4. Prompt Regression Catalog

- [ ] 4.1 Enumerate suites: planner, coder, reviewer, escalation, role-boundary, prompt-injection corpus.
- [ ] 4.2 Specify recorded fixtures, fixture refresh dual-review, and merge-blocking semantics.
- [ ] 4.3 Specify the air-gapped determinism contract.

## 5. CI Integration

- [ ] 5.1 Specify nightly chaos cron, weekly fuzz cron, and per-PR prompt regression triggers.
- [ ] 5.2 Specify per-PR opt-in labels (`chaos`, `fuzz`).
- [ ] 5.3 Specify failure-routing to escalation sinks.

## 6. Observability

- [ ] 6.1 Enumerate the metrics and alerts in `design.md`.
- [ ] 6.2 Define a triage SLA for fuzz crashes.

## 7. Verification (Specification Phase)

- [ ] 7.1 Confirm the spec preserves Tier 1 invariants.
- [ ] 7.2 Confirm both deployment profiles can run chaos, fuzz, and prompt regression offline.
- [ ] 7.3 Confirm escalation sinks are referenced, not invented.

## 8. Implementation (Deferred)

- [ ] 8.1 Implementation of scenarios, fuzz targets, fixtures, and CI wiring is deferred to a follow-up apply.
