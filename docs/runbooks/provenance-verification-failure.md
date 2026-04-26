# Runbook: SLSA Provenance Verification Failure

**Severity:** SEV2
**Owner:** Platform team
**Alert:** `admission_provenance_denied_total`

## Symptoms

- Pods fail to schedule with Kyverno provenance verification errors.
- Alert fires: `admission_provenance_denied_total > 0` over 5 minutes.
- Deployment rollout stalls.

## Diagnosis

1. Check Kyverno admission logs:
   ```bash
   kubectl logs -n kyverno -l app.kubernetes.io/name=kyverno --tail=200
   ```

2. Identify the failing image and missing attestation:
   ```bash
   kubectl get events --field-selector reason=FailedCreate -A
   ```

3. Verify the provenance attestation manually:
   ```bash
   cosign verify-attestation <image-ref> \
     --type slsaprovenance \
     --certificate-identity-regexp="https://github.com/dev-squad/.*" \
     --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
   ```

## Resolution

### If the provenance attestation is missing

1. Check if the SLSA generator job failed in CI:
   ```bash
   gh run list --workflow=supply-chain-hardening.yml --limit=5
   ```

2. Re-run the CI pipeline to regenerate the provenance:
   ```bash
   gh run rerun <run-id>
   ```

3. Verify the attestation was attached:
   ```bash
   cosign download attestation <image-ref>
   ```

### If a temporary exception is required

1. Create an admission exception with dual approval:
   ```bash
   curl -X POST https://<api>/api/v1/admin/admission-exceptions/ \
     -H "Content-Type: application/json" \
     -d '{
       "tenant_id": "<tenant>",
       "team_id": "<team>",
       "policy_name": "require-slsa-provenance",
       "image_reference": "<image-ref>",
       "rationale": "Emergency deployment while provenance generation is repaired",
       "approved_by": "<super_admin_1>",
       "second_approver": "<super_admin_2>",
       "expires_at": "2026-04-27T00:00:00Z"
     }'
   ```

### If Rekor is unreachable (air-gapped)

1. Verify the internal Rekor mirror is healthy.
2. Check that the SLSA generator is configured to use the internal Rekor endpoint.
3. If the mirror is down, follow the Sigstore mirror recovery runbook.

## Prevention

- Ensure the `slsa-framework/slsa-github-generator` action is present in CI.
- Monitor `admission_provenance_denied_total` for trends.
- Run quarterly provenance verification drills.
