# Runbook: Provider Breaker Open

## Trigger

- `devsquad_provider_circuit_breaker_state == 0` for a provider.

## Checks

- Inspect `provider_health_events` for the latest failure and half-open transitions.
- Confirm whether the deployment profile is `connected` or `air_gapped`.
- Verify fallback routing stayed within the model catalog allowlist.

## Response

- In connected mode, validate upstream provider availability and recover with `move_to_half_open`.
- In air-gapped mode, keep fail-closed behaviour until the self-hosted endpoint is healthy.
- Record evidence summary and operator rationale before reopening traffic.
