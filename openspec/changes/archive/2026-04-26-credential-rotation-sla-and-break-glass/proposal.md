## Why

The constitution mandates a credential-rotation SLA and dual-control break-glass. PLAN.md specifies 90-day rotation, overdue alerts that block new runs, staged KEK rotation with DEK re-wrap, and a `rotate_kek.sh` drill script. Phase 3 introduced envelope encryption but did not deliver the SLA enforcement, the break-glass flow, or the KEK-rotation operator surface.

## What Changes

- Add `next_rotation_due` tracking per credential record; alert when within 14 days and block new ticket acceptance when overdue.
- Implement dual-control break-glass access: two super_admin approvers, audited rationale, time-bounded token, immutable evidence.
- Implement staged KEK rotation: introduce a new KEK version, dual-read during re-wrap, background re-wrap job, switch default KEK after completion, retire old KEK.
- Provide `rotate_kek.sh` operator script and an in-cluster quarterly drill Job; surface drill status on the status page.
- Expose credential-rotation health via metrics and the admin UI status panel.

## Capabilities

### New Capabilities

- `credential-rotation-and-break-glass`: contract for per-credential SLA, break-glass dual-control, KEK rotation staging, and drill evidence.

### Modified Capabilities

- `tenant-isolation-and-credentials`: every sensitive credential record now carries rotation metadata and supports dual-read during KEK rotation.

## Impact

- Code: `backend/src/backend/security/credentials.py`, new `security/break_glass.py`, admin UI status panel entries.
- Schema: `credential_rotation_schedule`, `break_glass_grants`, `kek_versions`.
- Secrets: KEK lives in KMS or Vault; DEKs wrapped and rewrapped; ciphertext never logged.
- Observability: rotation-overdue alerts, KEK-rotation progress metrics, break-glass open-session alerts.
- Tests: drill script in CI; chaos test for mid-rotation pod restart.
- Constitution alignment: Tier 1 rotation-SLA and dual-control break-glass preserved.
