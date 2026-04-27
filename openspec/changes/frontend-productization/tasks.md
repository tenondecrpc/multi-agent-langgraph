## 1. Artifact Alignment

- [ ] 1.1 Confirm scope respects Tier 2 degradations from the constitution (read-only editor, bundled sprites, English-only).
- [ ] 1.2 Reconcile with the API versioning archived change so client generation is sourced from `/api/v1/openapi.json`.

## 2. Typed Client Contract

- [ ] 2.1 Specify the generator, source document path, output directory, and CI regeneration check.
- [ ] 2.2 Specify failure mode when the OpenAPI document drifts.

## 3. Live Data Surfaces

- [ ] 3.1 Specify polling cadence per surface (table in `design.md`).
- [ ] 3.2 Specify role-aware empty states and tenant-context display rules.
- [ ] 3.3 Specify structured error toasts with runbook links.

## 4. Graph Editor Stage 1

- [ ] 4.1 Specify shadow-mode preview UX, diff rendering, and validation feedback.
- [ ] 4.2 Specify the deferred stage 2 follow-up parity task.

## 5. Sprite Asset Management

- [ ] 5.1 Specify metadata CRUD over the admin endpoint.
- [ ] 5.2 Specify the deferred upload flow and 501 contract.

## 6. Accessibility And Localization

- [ ] 6.1 Specify the component-level accessibility contract test.
- [ ] 6.2 Specify the locale extraction tool, catalog layout, and missing-translation CI check.
- [ ] 6.3 Specify the Spanish enablement toggle.

## 7. Verification (Specification Phase)

- [ ] 7.1 Confirm Tier 2 degradations remain explicit and have parity follow-ups where applicable.
- [ ] 7.2 Confirm the spec preserves Tier 1 invariants (no client-side enforcement substitution).

## 8. Implementation (Deferred)

- [ ] 8.1 Implementation of clients, features, accessibility tests, and CI checks is deferred to a follow-up apply.
