# Runbook: Canary Rollback

## Trigger

Argo Rollouts `AnalysisTemplate` detects an SLO breach during a canary rollout step.

## Symptoms

- Rollout status shows `Progressing` with failed analysis
- Prometheus alerts fire for error rate, latency p95, or circuit-breaker events
- Rollout pauses at the current canary weight

## Steps

### 1. Confirm the Rollback

```bash
kubectl argo rollouts get rollout dev-squad-backend -n <namespace>
kubectl argo rollouts get rollout dev-squad-worker -n <namespace>
```

Check the analysis run status:

```bash
kubectl argo rollouts get analysisrun <analysis-run-name> -n <namespace>
```

### 2. Execute Manual Rollback (if automatic rollback fails)

```bash
kubectl argo rollouts abort dev-squad-backend -n <namespace>
kubectl argo rollouts undo dev-squad-backend -n <namespace>
```

### 3. Verify Rollback Completion

```bash
kubectl argo rollouts status dev-squad-backend -n <namespace>
```

Confirm the previous replica set is serving 100% traffic.

### 4. Investigate Root Cause

- Check Prometheus dashboards for the breached metric
- Review recent commits between the previous and current image
- Check circuit-breaker state in Redis
- Check DLQ depth in PostgreSQL

### 5. Post-Rollback Actions

- Document the rollback in the incident log
- Create a follow-up ticket for root cause analysis
- If the issue is reproducible, add a regression test to the chaos suite

## Escalation

If rollback fails or the previous version also shows degradation:

1. Engage the on-call SRE
2. Consider disabling the affected subsystem via kill switch
3. Page the team lead if customer-facing impact persists > 15 minutes

## Related Runbooks

- `kill-switch-activation.md`
- `flag-service-outage.md`
