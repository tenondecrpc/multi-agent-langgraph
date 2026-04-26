# Runbook: Image Signature Verification Failure

**Severity:** SEV2
**Owner:** Platform team
**Alert:** `admission_signature_denied_total`

## Symptoms

- Pods fail to schedule with Kyverno signature verification errors.
- Alert fires: `admission_signature_denied_total > 0` over 5 minutes.
- Deployment rollout stalls.

## Diagnosis

1. Check Kyverno admission logs:
   ```bash
   kubectl logs -n kyverno -l app.kubernetes.io/name=kyverno --tail=200
   ```

2. Identify the failing image:
   ```bash
   kubectl get events --field-selector reason=FailedCreate -A
   ```

3. Verify the image signature manually:
   ```bash
   cosign verify <image-ref> \
     --certificate-identity-regexp="https://github.com/dev-squad/.*" \
     --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
   ```

## Resolution

### If the image is legitimately unsigned

1. Check if the CI signing job failed:
   ```bash
   gh run list --workflow=supply-chain-hardening.yml --limit=5
   ```

2. If the signing job failed, re-run the CI pipeline:
   ```bash
   gh run rerun <run-id>
   ```

3. If the image was built locally or outside CI, sign it:
   ```bash
   cosign sign --yes <image-ref>
   ```

### If a temporary exception is required

1. Create an admission exception with dual approval:
   ```bash
   curl -X POST https://<api>/api/v1/admin/admission-exceptions/ \
     -H "Content-Type: application/json" \
     -d '{
       "tenant_id": "<tenant>",
       "team_id": "<team>",
       "policy_name": "require-image-signature",
       "image_reference": "<image-ref>",
       "rationale": "Emergency deployment while CI pipeline is repaired",
       "approved_by": "<super_admin_1>",
       "second_approver": "<super_admin_2>",
       "expires_at": "2026-04-27T00:00:00Z"
     }'
   ```

2. Monitor the exception expiry and ensure the image is re-signed before expiration.

### If Rekor is unreachable (air-gapped)

1. Verify the internal Rekor mirror is healthy:
   ```bash
   kubectl get pods -n sigstore -l app=rekor
   ```

2. Check the internal Rekor endpoint:
   ```bash
   curl -s https://rekor.internal.sigstore.svc.cluster.local/api/v1/log
   ```

3. If the mirror is down, follow the Sigstore mirror recovery runbook.

## Prevention

- Ensure all CI pipelines include the `image-signing` job.
- Monitor `admission_signature_denied_total` for trends.
- Run quarterly signature verification drills.
