## Context

LLM usage is central to the product and therefore central to cost, fairness, and reliability risk. This phase isolates the provider router, budget system, metering pipeline, and model-catalog rules from `docs/PLAN.md` so later implementation work cannot treat them as optional operational details.

## Goals / Non-Goals

**Goals:**
- Define provider routing and failover behavior that works across a horizontally scaled worker pool.
- Define race-free budget enforcement that protects per-ticket and per-team limits.
- Define auditable metering and billing export behavior that does not require the billing system to query operational tables directly.
- Define model-catalog and token-limit validation rules, including air-gapped fallback constraints.

**Non-Goals:**
- Tenant auth, webhook security, or prompt-safety enforcement.
- Graph configuration and shadow-mode activation behavior.
- Frontend dashboard interaction design.
- Release engineering and observability alert policy beyond what is needed for LLM governance contracts.

## Decisions

- Provider health and circuit-breaker state are shared through Redis so the worker pool reacts as one system rather than as isolated processes.
- Every LLM call carries a full budget context and must reserve budget before the provider call rather than checking cost after the fact.
- Budget reservations use worst-case estimation and post-call settlement so concurrency cannot overspend the configured caps.
- Metering is both an operational control plane and a billing source of truth, but billing consumers read rollups or exports rather than directly querying live operational tables.
- Model identifiers are validated against a pinned catalog. Unknown IDs fail configuration rather than silently falling back.
- Air-gapped mode keeps the same routing contract while restricting both primary and fallback models to self-hosted provider surfaces.

## Risks / Trade-offs

- Accurate budget reservation requires more upfront modeling work than naïve post-hoc metering, but it prevents race conditions that would violate budget caps.
- Shared breaker state adds Redis dependence to provider routing, but avoiding shared state would waste capacity during outages and produce inconsistent operator behavior.
- Billing export introduces a second consumer for metering data, so schema stability becomes a product contract rather than a convenience.
