# Runbook: Flag Service Outage

## Trigger

Unleash or LaunchDarkly becomes unavailable, preventing feature flag evaluation.

## Symptoms

- Feature flag client logs warnings about provider unavailability
- Kill switches fall back to PostgreSQL mirror
- Mirror TTL may expire if outage persists > 300 seconds

## Impact Assessment

### Low Impact (Outage < 5 minutes)

- PostgreSQL mirror serves last-known flag state
- Kill switches remain functional via mirror
- No operator action required

### Medium Impact (Outage 5-30 minutes)

- Mirror TTL may expire; kill switches fail closed (disabled)
- New flag evaluations return default values
- Flag toggles are queued but not applied

### High Impact (Outage > 30 minutes)

- All kill switches are in fail-closed state
- Subsystems may be partially disabled
- Manual intervention required

## Steps

### 1. Confirm Flag Service Status

```bash
# Check Unleash health
curl -f http://unleash-web:4242/health || echo "Unleash is down"

# Check LaunchDarkly status (external)
curl -f https://status.launchdarkly.com/api/v2/status.json
```

### 2. Check PostgreSQL Mirror Status

```bash
psql -c "SELECT flag_key, enabled, mirror_synced_at,
  NOW() - mirror_synced_at AS staleness
  FROM feature_flag_state
  ORDER BY staleness DESC;"
```

### 3. If Mirror is Stale (TTL Expired)

Kill switches are in fail-closed state. Assess which subsystems are affected:

```bash
psql -c "SELECT flag_key, enabled, owner, description
  FROM feature_flag_state
  WHERE is_kill_switch = true AND enabled = false;"
```

### 4. Restore Flag Service

For Unleash (self-hosted):

```bash
kubectl rollout restart deployment/unleash-web -n <namespace>
kubectl rollout status deployment/unleash-web -n <namespace>
```

For LaunchDarkly (customer-owned):

- Contact the LaunchDarkly account administrator
- Check the LaunchDarkly status page
- Wait for service restoration

### 5. Verify Mirror Resync

After flag service restoration, verify the mirror resyncs:

```bash
psql -c "SELECT flag_key, mirror_synced_at,
  NOW() - mirror_synced_at AS staleness
  FROM feature_flag_state
  ORDER BY staleness DESC
  LIMIT 10;"
```

Staleness should be < 30 seconds after resync.

### 6. Re-enable Disabled Kill Switches

If kill switches were in fail-closed state, re-enable them via the flag service UI or API.

### 7. Post-Outage Actions

- Document the outage in the incident log
- Review mirror sync interval (default: 30 seconds)
- Consider increasing TTL if outages are frequent
- Create a follow-up ticket if root cause is unresolved

## Prevention

- Run Unleash with at least 2 replicas
- Configure health probes and auto-restart
- Monitor mirror staleness as a Prometheus metric
- Include flag service in chaos testing scenarios

## Escalation

If flag service cannot be restored within 30 minutes:

1. Engage the platform team
2. Consider manual flag state management via PostgreSQL
3. Page the team lead if customer-facing impact persists

## Related Runbooks

- `canary-rollback.md`
- `kill-switch-activation.md`
