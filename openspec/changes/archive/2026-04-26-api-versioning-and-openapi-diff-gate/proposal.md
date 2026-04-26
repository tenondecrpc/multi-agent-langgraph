## Why

The constitution mandates public API versioning and diff gates. PLAN.md specifies `/api/v1` harness, `openapi-diff` blocking on breaking changes, `Deprecation` and `Sunset` headers, `Accept-Version` negotiation, SSE `schema_version`, and versioned metering export with 12-month parallel support. Phase 2 established the API surface; this change adds the versioning harness and CI diff gate.

## What Changes

- Adopt `/api/v1/` prefix on all external routes; internal admin routes carry the same discipline.
- Add CI `openapi-diff` step: compare PR branch OpenAPI to main; block on breaking changes unless labelled `breaking-change-approved` with super_admin sign-off.
- Add `Deprecation` and `Sunset` response headers and structured deprecation logs on every call to a deprecated route.
- Support `Accept-Version` request header and an SSE `schema_version` event for streaming endpoints.
- Version metering export schema with 12-month parallel support; older versions continue to be generated until the sunset date.
- Define compatibility-epoch lifecycle: deprecation -> parallel support -> sunset; each step auditable.

## Capabilities

### New Capabilities

- `api-versioning-and-compatibility`: route versioning, OpenAPI diff policy, deprecation lifecycle, SSE schema version, metering export parallel support.

### Modified Capabilities

- `api-surface-and-versioning`: adds explicit diff-gate enforcement and deprecation headers.

## Impact

- Code: FastAPI router prefix, OpenAPI generation, SSE event envelope, CI workflow step.
- Schema: `api_deprecations` catalog (route, version, deprecated_at, sunset_at, rationale).
- Observability: deprecated-route hit-count per tenant, sunset-window alerts.
- Docs: publish OpenAPI bundle and version timeline.
- Constitution alignment: Tier 1 preserved; diff gate is CI-blocking.
