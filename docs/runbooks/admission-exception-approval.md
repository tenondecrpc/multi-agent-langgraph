# Runbook: Admission Exception Approval and Management

**Severity:** SEV3
**Owner:** Platform team
**Alert:** `admission_exception_expiring_soon`

## Symptoms

- Alert fires: admission exceptions expiring within 24 hours.
- Audit log shows new exception creation.
- Operator dashboard shows active exceptions.

## Diagnosis

1. List active exceptions:
   ```bash
   curl -s https://<api>/api/v1/admin/admission-exceptions/ \
     | jq '.exceptions[] | {exception_id, policy_name, image_reference, expires_at}'
   ```

2. Check exception details:
   ```bash
   curl -s https://<api>/api/v1/admin/admission-exceptions/<exception_id> \
     | jq '.'
   ```

3. Verify dual approval:
   - Confirm `approved_by` and `second_approver` are different super_admin users.
   - Check audit trail for approval timestamps.

## Resolution

### If an exception is about to expire

1. Determine if the underlying issue has been resolved:
   - Has the image been re-signed?
   - Has the provenance been attached?
   - Has the digest been pinned?

2. If resolved, let the exception expire naturally.

3. If not resolved, create a new exception with updated rationale:
   ```bash
   curl -X POST https://<api>/api/v1/admin/admission-exceptions/ \
     -H "Content-Type: application/json" \
     -d '{
       "tenant_id": "<tenant>",
       "team_id": "<team>",
       "policy_name": "<policy>",
       "image_reference": "<image-ref>",
       "rationale": "Extended exception: <updated rationale>",
       "approved_by": "<super_admin_1>",
       "second_approver": "<super_admin_2>",
       "expires_at": "2026-04-28T00:00:00Z"
     }'
   ```

### If an exception needs to be revoked early

1. Revoke the exception:
   ```bash
   curl -X POST https://<api>/api/v1/admin/admission-exceptions/<exception_id>/revoke \
     -H "Content-Type: application/json" \
     -d '{
       "revoked_by": "<super_admin>",
       "revoke_reason": "Security review determined the exception is no longer justified"
     }'
   ```

2. Verify the affected pods are replaced with compliant images.

### Quarterly exception audit

1. Export all exceptions for the quarter:
   ```bash
   curl -s https://<api>/api/v1/admin/admission-exceptions/?include_revoked=true \
     | jq '.exceptions' > exceptions-q1-2026.json
   ```

2. Review for patterns:
   - Are the same images repeatedly excepted?
   - Are exceptions consistently renewed?
   - Is dual approval being bypassed?

3. Report findings to the security team.

## Prevention

- Set exception expiry to the minimum necessary duration.
- Automate exception expiry alerts at 48h, 24h, and 1h.
- Require post-incident review for any exception used in production.
