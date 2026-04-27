# Runbook: Air-Gapped Deployment

## Scope

Use this runbook for customer-owned `air_gapped` deployments. The profile must not rely on vendor-operated control planes, external LLM providers, external statuspage sync, or vendor telemetry egress.

## Install Checks

1. Render the chart:
   ```bash
   helm template dev-squad ./helm -f ./helm/values.yaml -f ./helm/values-air-gapped.yaml
   ```
2. Confirm `statusPageSync.enabled: false` and no `dev-squad-status-page-sync` CronJob is rendered.
3. Confirm `langsmith.enabled: false`, `DO_NOT_TRACK=1`, and `LANGCHAIN_TRACING_V2=false`.
4. Confirm the NetworkPolicy allows only internal DNS plus the internal embedding or model endpoint required by the deployment.
5. Confirm Vault has been seeded offline before backend pods start.
6. Confirm `BACKEND_DEPLOYMENT_PROFILE=air_gapped` and `BACKEND_PROVIDER_OPENCODE_GO_ENDPOINT` are rendered in the backend pod template.
7. Confirm no OpenAI or Anthropic API key is present in Helm values, Kubernetes Secrets, ExternalSecrets, or backend env.

## Offline Vault Bootstrap

Run the bootstrap from an operator workstation inside the disconnected environment:

```bash
VAULT_ADDR=https://vault.example.internal \
VAULT_TOKEN=<operator-held-token> \
BACKEND_DATABASE_URL=<postgres-url> \
BACKEND_REDIS_URL=<redis-url> \
BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY=<wrapping-key> \
sh scripts/bootstrap_air_gapped_vault.sh
```

Operator key custody rules:

- Unseal keys and bootstrap tokens stay with the customer operator team and are never committed, copied into Helm values, or logged.
- Use a short-lived bootstrap token for the maintenance window, then revoke it after the script completes.
- Store the wrapping key only in Vault. Backend pods receive it through External Secrets Operator.
- Do not use Vault dev mode. Air-gapped startup now fails if the deployment profile has no PostgreSQL, Redis, and Vault-backed encryption configuration.

## Internal Status Fallback

The public statuspage sync is disabled in `air_gapped`. Operators must use one of these internal surfaces:

- Admin UI public status tile.
- `GET /api/v1/status-page` from inside the customer network.
- Prometheus and Alertmanager dashboards inside the customer-owned cluster.

## Drill

1. Block external DNS and outbound internet egress in the test namespace.
2. Run a smoke ticket that exercises planner, tester, reviewer, and PR guard paths with the self-hosted OpenCode Go provider.
3. Confirm no pod attempts to reach LangSmith, PostHog, hosted LLM APIs, or an external statuspage endpoint.
4. Record Helm render output, NetworkPolicy evidence, and `/api/v1/status-page` output.
5. Confirm provider-health output references only `opencode-go` endpoints.

## Recovery

1. If pods fail readiness because a required internal endpoint is unavailable, keep ingress closed and fix the internal dependency.
2. If an external egress attempt is detected, keep the release blocked, capture the offending destination, and open a security review.
3. Resume rollout only after the air-gapped render and smoke checks pass.

## Escalation

Escalate as SEV1 for external egress attempts involving secrets, tenant data, or model payloads. Escalate as SEV2 for missing internal dependencies that block ticket execution without data exposure.
