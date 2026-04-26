## 1. Artifact Alignment

- [ ] 1.1 Reconcile with Phase 3 envelope-encryption spec and the active persistence change.

## 2. Rotation SLA

- [ ] 2.1 Add `credential_rotation_schedule` table; daily evaluator job.
- [ ] 2.2 Wire warning alerts at 14-day window; wire blocking behavior when overdue.
- [ ] 2.3 Admin UI surfaces rotation status and upcoming due dates (accessibility non-negotiable subset).

## 3. Break-Glass

- [ ] 3.1 Add `break_glass_grants` table and endpoints; require dual super_admin approval.
- [ ] 3.2 Time-bounded token issuance; audit on create, approve, expire, revoke.
- [ ] 3.3 Paging integration so approvers are notified.

## 4. KEK Rotation

- [ ] 4.1 Add `kek_versions` table; enable dual-read in the persistence encryption helper.
- [ ] 4.2 Implement idempotent background re-wrap job with resumable checkpoints.
- [ ] 4.3 Provide `rotate_kek.sh` and the quarterly drill Job.

## 5. Observability

- [ ] 5.1 Metrics: overdue-credential count, break-glass open count, KEK-rotation progress, drill pass/fail.
- [ ] 5.2 Alerts and runbooks under `docs/`.

## 6. Verification

- [ ] 6.1 `uv run --project backend pytest` including drill simulation.
- [ ] 6.2 Chaos test: kill worker mid-rewrap; verify resume.

## 7. Archive

- [ ] 7.1 Archive after a real quarterly drill posts evidence.
