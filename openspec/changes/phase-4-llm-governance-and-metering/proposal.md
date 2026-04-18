## Why

The system depends on multiple LLM roles, provider failover, strict budget controls, and auditable metering. `docs/PLAN.md` describes those controls in depth, but they need their own OpenSpec phase so cost and reliability behavior are planned before implementation starts.

## What Changes

- Define provider routing, per-role model defaults, fallback behavior, and Redis-shared circuit-breaker requirements.
- Define budget governance, including atomic reservations, bounded ticket and team caps, and escalation behavior.
- Define metering, billing rollups, export, reconciliation, and invoice evidence requirements.
- Define model-catalog validation and per-role token-cap behavior, including air-gapped override rules.
- Keep this phase SDD-only. No provider SDK integration, Redis scripts, or billing code is introduced in this change.
- Classify this phase as Tier 1 for provider failover and budget governance, with Tier 2 billing-export degradation handled explicitly in the relevant specs.

## Capabilities

### New Capabilities
- `provider-routing-and-failover`: Per-role model defaults, provider health, shared circuit breaker, failover, and all-providers-down behavior.
- `budget-governance`: Ticket and team budget caps, atomic reservations, settlement, and escalation behavior.
- `llm-metering-and-billing`: Usage recording, billing rollups, export contracts, rate-card versioning, and reconciliation expectations.
- `model-catalog-and-token-caps`: Pinned model catalog, validation, per-role token ceilings, and air-gapped fallback catalog rules.

### Modified Capabilities
- None.

## Impact

- Future provider router and model selection code.
- Redis-based health and budget reservation mechanisms.
- PostgreSQL metering schema and billing export design.
- Admin configuration and observability work that depends on accurate provider and cost behavior.
