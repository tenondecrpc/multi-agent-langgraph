## 1. Artifact Alignment

- [ ] 1.1 Compose with Phase 7 observability spec; extend rather than overlap.

## 2. Status Endpoint

- [ ] 2.1 Implement `/api/v1/status-page` with whitelist schema and contract tests.
- [ ] 2.2 Admin UI tile reads the endpoint; accessibility non-negotiable subset verified.

## 3. Sync Job

- [ ] 3.1 CronJob posting to statuspage endpoint in connected profile.
- [ ] 3.2 Disabled in air-gapped profile; documented fallback.

## 4. Severity And Paging

- [ ] 4.1 Define SEV1/2/3; document on-call rotation and escalation matrix.
- [ ] 4.2 PagerDuty integration via External Secrets Operator.

## 5. Runbook Corpus

- [ ] 5.1 Author `all-providers-down.md` and `air-gapped-deployment.md`.
- [ ] 5.2 Author a runbook for every existing paging alert.
- [ ] 5.3 CI lint verifying `runbook_url` on every paging alert.

## 6. Verification

- [ ] 6.1 Contract test on status-page schema.
- [ ] 6.2 Paging drill in staging (SEV1 synthetic alert).

## 7. Archive

- [ ] 7.1 Archive after a successful paging drill evidence bundle.
