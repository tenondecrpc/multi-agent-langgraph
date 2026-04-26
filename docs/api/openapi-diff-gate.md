# OpenAPI Diff Gate

The public API contract is generated per major version from FastAPI and compared in CI.

The GitHub Actions workflow starts in warn mode for the first release window:

- `OPENAPI_DIFF_MODE=warn` reports breaking changes without blocking.
- After the transition release, change the workflow value to `block`.
- In block mode, breaking changes fail unless the pull request has the `breaking-change-approved` label and a matching JSONL record in `docs/api/breaking-change-approvals.jsonl`.

Approval records must include:

- `pr_number`
- `head_sha`
- `label`: `breaking-change-approved`
- `issued_by`
- `issued_by_role`: `super_admin`
- `rationale`
- `created_at`

CI emits an audit artifact for every attempted bypass.
