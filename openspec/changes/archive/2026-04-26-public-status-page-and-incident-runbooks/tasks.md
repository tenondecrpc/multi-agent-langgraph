## 1. Artifact Alignment

- [x] 1.1 Compose with Phase 7 observability spec; extend rather than overlap.

## 2. Status Endpoint

- [x] 2.1 Implement `/api/v1/status-page` with whitelist schema and contract tests.
- [x] 2.2 Admin UI tile reads the endpoint; accessibility non-negotiable subset verified.

## 3. Sync Job

- [x] 3.1 CronJob posting to statuspage endpoint in connected profile.
- [x] 3.2 Disabled in air-gapped profile; documented fallback.

## 4. Severity And Paging

- [x] 4.1 Define SEV1/2/3; document on-call rotation and escalation matrix.
- [x] 4.2 PagerDuty integration via External Secrets Operator.

## 5. Runbook Corpus

- [x] 5.1 Author `all-providers-down.md` and `air-gapped-deployment.md`.
- [x] 5.2 Author a runbook for every existing paging alert.
- [x] 5.3 CI lint verifying `runbook_url` on every paging alert.

## 6. Verification

- [x] 6.1 Contract test on status-page schema.
- [x] 6.2 Paging drill in staging (SEV1 synthetic alert).

## 7. Archive

- [x] 7.1 Archive after a successful paging drill evidence bundle.
