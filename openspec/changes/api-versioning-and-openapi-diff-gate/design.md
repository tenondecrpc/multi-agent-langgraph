# Design: API Versioning And OpenAPI Diff Gate

## Context

FastAPI auto-generates OpenAPI. Without a versioning harness and a diff gate, breaking changes can land silently. PLAN.md ties the public API contract to integrator SLAs.

## Goals / Non-Goals

### Goals

- Predictable `/api/v<major>/` path scheme.
- CI gate that blocks breaking changes without explicit approval.
- Deprecation visibility on every response and in logs.
- Content negotiation via `Accept-Version`.

### Non-Goals

- No support for per-field deprecation of non-public internal APIs.
- No runtime multi-version engine; versioning is path-based and explicit.

## Decisions

### Decision: Path-based versioning with single active major per route

All public routes carry a `/api/v<major>/` prefix. A route may have parallel majors active only during a deprecation window. OpenAPI emits one spec per active major.

### Decision: openapi-diff CI step is authoritative

A CI step generates the current branch OpenAPI and diffs it against main. Breaking changes (removed endpoints, removed required fields, type narrowings) fail the build unless the PR carries the `breaking-change-approved` label issued by super_admin with rationale.

### Decision: Deprecation lifecycle

Each route has a `Deprecation` header once deprecated and a `Sunset` header with ISO date. The `api_deprecations` table tracks timeline. A scheduled job alerts when a sunset window is approaching without client migration evidence (from deprecation-hit metrics).

### Decision: Metering export parallel support

Metering exports emit `v1`, `v2`, ... formats; new majors run alongside old until the sunset date 12 months later. Both formats are exposed under distinct paths.

## Risks / Trade-offs

- Diff-gate false positives. Mitigated by explicit approval label.
- Operator burden in tracking sunsets. Mitigated by admin UI surface and alerts.

## Migration Plan

1. Prefix all routes with `/api/v1`; add redirect from unversioned paths during a transition window.
2. Wire CI diff gate; start in warn-only mode; flip to block after one release.
3. Add deprecation headers and catalog table.
4. Implement metering-export version harness.
