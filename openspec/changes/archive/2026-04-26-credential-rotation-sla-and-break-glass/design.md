# Design: Credential Rotation SLA And Break-Glass

## Context

Envelope encryption exists (Phase 3). What does not exist: an enforced SLA on credential age, a dual-control break-glass flow, and a KEK-rotation procedure that is safe under running traffic.

## Goals / Non-Goals

### Goals

- 90-day default rotation SLA per credential kind (Jira, GitHub App, GitHub PAT, LLM provider keys, OIDC client secrets).
- Dual super_admin approval for break-glass, with immutable audit evidence.
- Staged KEK rotation supporting dual-read and zero-downtime cutover.
- Operator drill script and quarterly drill Job.

### Non-Goals

- No change to the envelope-encryption algorithm or to KMS/Vault vendor selection.
- No weakening of least-privilege RBAC; break-glass remains time-bounded and explicit.

## Decisions

### Decision: Per-credential rotation schedule

Table `credential_rotation_schedule` keys on `(tenant_id, credential_kind, credential_id)` with `rotated_at`, `next_rotation_due`, `overdue`. Overdue credentials block ticket acceptance for the tenant and team scope. A scheduled job evaluates thresholds daily.

### Decision: Break-glass dual control

Table `break_glass_grants` captures `requested_by`, `approved_by`, `reason`, `scope`, `granted_at`, `expires_at`, `revoked_at`. The grant is only valid after two distinct super_admins approve. A grant emits an audit event on creation and on expiration.

### Decision: Staged KEK rotation with dual-read

Table `kek_versions` captures `kek_id`, `kms_ref`, `introduced_at`, `retired_at`. Rotation proceeds as: introduce new KEK -> configure dual-read so readers can decrypt old- and new-wrapped DEKs -> background job re-wraps DEKs -> switch default KEK -> wait for retention window -> retire old KEK. All steps are auditable.

### Decision: Drill surface

`rotate_kek.sh` is an operator-invoked script that runs the staged flow in a non-prod environment and produces a structured evidence bundle. A quarterly in-cluster drill Job runs the same flow against a dedicated test tenant and posts the result to the status page.

## Risks / Trade-offs

- Mid-rotation pod restart. Mitigated by idempotent re-wrap job with checkpoint of processed DEK IDs.
- Human approval latency. Mitigated by paging integration and explicit SLA.
- Break-glass abuse. Mitigated by time-bounded tokens and audit retention aligned with the data-retention policy.

## Migration Plan

1. Add schedule table and daily job; start emitting warnings without blocking.
2. Introduce new KEK version infrastructure in staging; drill re-wrap.
3. Enable blocking when overdue after one release of warnings.
4. Turn on break-glass flow; document and train super_admins.
