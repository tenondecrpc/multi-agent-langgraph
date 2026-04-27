## 1. Artifact Alignment

- [x] 1.1 Confirm scope respects Tier 2 degradations from the constitution (read-only editor, bundled sprites, English-only).
- [x] 1.2 Reconcile with the API versioning archived change so client generation is sourced from `/api/v1/openapi.json`.

## 2. Typed Client Contract

- [x] 2.1 Specify the generator, source document path, output directory, and CI regeneration check.
- [x] 2.2 Specify failure mode when the OpenAPI document drifts.

## 3. Live Data Surfaces

- [x] 3.1 Specify polling cadence per surface (table in `design.md`).
- [x] 3.2 Specify role-aware empty states and tenant-context display rules.
- [x] 3.3 Specify structured error toasts with runbook links.

## 4. Graph Editor Stage 1

- [x] 4.1 Specify shadow-mode preview UX, diff rendering, and validation feedback.
- [x] 4.2 Specify the deferred stage 2 follow-up parity task.

## 5. Sprite Asset Management

- [x] 5.1 Specify metadata CRUD over the admin endpoint.
- [x] 5.2 Specify the deferred upload flow and 501 contract.

## 6. Accessibility And Localization

- [x] 6.1 Specify the component-level accessibility contract test.
- [x] 6.2 Specify the locale extraction tool, catalog layout, and missing-translation CI check.
- [x] 6.3 Specify the Spanish enablement toggle.

## 7. Verification (Specification Phase)

- [x] 7.1 Confirm Tier 2 degradations remain explicit and have parity follow-ups where applicable.
- [x] 7.2 Confirm the spec preserves Tier 1 invariants (no client-side enforcement substitution).

## 8. Implementation (Deferred)

- [x] 8.1 Implementation of clients, features, accessibility tests, and CI checks is deferred to a follow-up apply.
