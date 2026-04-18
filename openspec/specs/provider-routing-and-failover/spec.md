# provider-routing-and-failover Specification

## Purpose
TBD - created by archiving change phase-4-llm-governance-and-metering. Update Purpose after archive.
## Requirements
### Requirement: Per-Role Model Defaults And Fallbacks

Each runtime role MUST have a default model assignment and MAY have a configured fallback model from an alternate provider or self-hosted surface.

#### Scenario: Role uses its configured default model
- **WHEN** a planner, coder, tester, reviewer, or PR creator invocation begins
- **THEN** the provider router selects the role's configured primary model when the provider is healthy and budget permits

#### Scenario: Fallback activates when the primary is unhealthy
- **WHEN** the primary provider for a role is unhealthy or unavailable
- **THEN** the router attempts the configured fallback path
- **AND** the failover remains subject to the same budget and policy checks as the primary path

### Requirement: Circuit Breaker State Is Shared Across Workers

Provider health and circuit-breaker state MUST be coordinated across the worker pool rather than tracked independently inside each worker process.

#### Scenario: Pool-wide failure opens the breaker
- **WHEN** provider failures cross the configured threshold within the shared failure window
- **THEN** the breaker opens for the provider across the pool
- **AND** later workers do not each rediscover the outage independently through repeated doomed calls

#### Scenario: Half-open recovery is bounded
- **WHEN** a provider moves from open toward recovery
- **THEN** only the configured bounded number of probe calls are allowed during the half-open window
- **AND** the provider does not return to general traffic until the recovery logic permits it

### Requirement: All-Providers-Down Behavior Preserves Runs

When every configured provider is unavailable, the runtime MUST pause and resume runs rather than silently losing progress.

#### Scenario: Run pauses on all-providers-down
- **WHEN** no healthy provider remains for the requested role and budget context
- **THEN** the current run checkpoints its state, records an explicit `all_providers_unavailable` escalation or pause reason, and becomes resumable

#### Scenario: Recovery resumes paused work
- **WHEN** at least one acceptable provider becomes healthy again
- **THEN** paused runs are resumed from their last checkpoint according to fair scheduling rules
- **AND** the resumed run does not restart from scratch or lose its pinned context

### Requirement: Air-Gapped Routing Remains Supported

The same routing contract MUST work in `air_gapped` deployments, with both primary and fallback models restricted to self-hosted provider surfaces.

#### Scenario: Air-gapped catalog excludes external providers
- **WHEN** the platform operates in `air_gapped` mode
- **THEN** model routing and failover stay within the self-hosted provider catalog
- **AND** the product does not assume external Anthropic or OpenAI connectivity

