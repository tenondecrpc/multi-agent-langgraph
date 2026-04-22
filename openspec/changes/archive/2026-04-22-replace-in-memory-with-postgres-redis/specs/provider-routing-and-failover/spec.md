## ADDED Requirements

### Requirement: Redis-Shared Circuit Breaker For Providers

Provider health and the circuit breaker SHALL be shared across workers via a Redis hash keyed by `(provider, region)` with TTL, protected by a Lua script for atomic updates. Historical incident evidence SHALL be persisted to PostgreSQL for audit.

#### Scenario: Breaker opens and every replica observes it
- **WHEN** a provider crosses the failure threshold
- **THEN** the Redis circuit-breaker state transitions to open atomically
- **AND** every replica refuses outbound calls to that provider until the half-open window
- **AND** a `provider_health_events` row is written to PostgreSQL

### Requirement: Air-Gapped-Safe Fail-Closed Fallback

When Redis is unreachable, the adapter SHALL apply the fail-closed policy declared in config. The adapter MUST NOT silently permit unbounded outbound calls.

#### Scenario: Redis unreachable in air-gapped deployment
- **WHEN** the Redis cluster is unavailable and the deployment is `air_gapped`
- **THEN** outbound provider calls are refused with a typed persistence error
- **AND** the event is observable and alertable
