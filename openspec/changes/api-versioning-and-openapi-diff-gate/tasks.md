## 1. Artifact Alignment

- [ ] 1.1 Confirm this change composes with Phase 2 api-surface-and-versioning archived spec.

## 2. Routing And OpenAPI

- [ ] 2.1 Prefix routes with `/api/v1/`; add transition redirect window.
- [ ] 2.2 Emit one OpenAPI document per active major.
- [ ] 2.3 Add `Accept-Version` negotiation and SSE `schema_version` event.

## 3. CI Diff Gate

- [ ] 3.1 Add openapi-diff step in CI; start in warn mode.
- [ ] 3.2 Flip to block after one release; require `breaking-change-approved` label bypass.
- [ ] 3.3 Audit label issuance as a super_admin action.

## 4. Deprecation Lifecycle

- [ ] 4.1 Add `api_deprecations` table and admin UI view of timeline.
- [ ] 4.2 Emit `Deprecation` and `Sunset` headers; log `api_deprecation_hit` metric.
- [ ] 4.3 Sunset-approaching alerts based on deprecation-hit traffic evidence.

## 5. Metering Export

- [ ] 5.1 Version metering export schema; serve v1 and v2 in parallel; define 12-month minimum window.
- [ ] 5.2 Reconciliation tests across versions.

## 6. Verification

- [ ] 6.1 `uv run --project backend ruff check` and `pytest` green.
- [ ] 6.2 Integration test that a breaking PR is blocked and a non-breaking PR passes.

## 7. Archive

- [ ] 7.1 Archive after one full deprecation lifecycle has been exercised.
