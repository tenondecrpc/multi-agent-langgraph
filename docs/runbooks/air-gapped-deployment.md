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
4. Confirm the NetworkPolicy allows only the internal embedding or model endpoint required by the deployment.
5. Confirm Vault has been seeded offline before backend pods start.

## Internal Status Fallback

The public statuspage sync is disabled in `air_gapped`. Operators must use one of these internal surfaces:

- Admin UI public status tile.
- `GET /api/v1/status-page` from inside the customer network.
- Prometheus and Alertmanager dashboards inside the customer-owned cluster.

## Drill

1. Block external DNS and outbound internet egress in the test namespace.
2. Run a smoke ticket that exercises planner, tester, reviewer, and PR guard paths with the self-hosted provider.
3. Confirm no pod attempts to reach LangSmith, PostHog, hosted LLM APIs, or an external statuspage endpoint.
4. Record Helm render output, NetworkPolicy evidence, and `/api/v1/status-page` output.

## Recovery

1. If pods fail readiness because a required internal endpoint is unavailable, keep ingress closed and fix the internal dependency.
2. If an external egress attempt is detected, keep the release blocked, capture the offending destination, and open a security review.
3. Resume rollout only after the air-gapped render and smoke checks pass.

## Escalation

Escalate as SEV1 for external egress attempts involving secrets, tenant data, or model payloads. Escalate as SEV2 for missing internal dependencies that block ticket execution without data exposure.
