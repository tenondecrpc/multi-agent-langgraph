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

## Provider And Budget Coverage

This phase locks down the LLM control plane required by the runtime and platform baselines.

| LLM concern | Contract outcome in this phase | Relationship to prior phases |
|---|---|---|
| Provider routing | Each runtime role keeps a primary model and optional fallback, with pool-wide health tracking. | Extends phase 1 role execution without changing the protected success path. |
| Circuit breaker state | Provider health is shared across workers instead of rediscovered per process. | Builds on phase 2 worker coordination and queue fairness assumptions. |
| Budget governance | Ticket and team caps use atomic reservations and later settlement. | Reuses phase 1 run identity and escalation semantics for budget failure paths. |
| All-providers-down handling | Runs pause at a checkpoint and resume later from pinned context. | Preserves phase 1 checkpoint lineage and phase 2 fair scheduling. |
| Air-gapped support | Connected and `air_gapped` deployments keep the same routing contract, but `air_gapped` restricts the catalog to self-hosted providers. | Preserves the phase 2 first-class `air_gapped` platform profile. |
| Metering and billing | Every call is attributable, rollups are reproducible, and exports remain bounded. | Later phase 6 UI and phase 7 observability consume this contract without redefining it. |

Required runtime reasons introduced by this phase:

- `budget_exhausted`
- `all_providers_unavailable`
- `provider_failover_exhausted`
- `orphaned_budget_reservation_detected`
- `billing_reconciliation_drift`

These reasons must be registered through the phase 1 escalation-sink model and observed through the phase 7 operations model.

## LLM Control Interfaces

### Future Provider Router Interface

```python
class ProviderSelection(BaseModel):
    provider_id: str
    model_id: str
    fallback_used: bool = False


class ProviderRouter(Protocol):
    async def select_model(
        self,
        role: Literal["planner", "coder", "tester", "reviewer", "pr_creator"],
        run_id: str,
        tenant_id: str,
        budget_context: "BudgetContext",
        deployment_profile: Literal["connected", "air_gapped"],
    ) -> ProviderSelection: ...
```

Router rules:

- Role-to-model selection starts from the pinned config snapshot and pinned model catalog version for the run.
- Provider selection must consult shared breaker state before choosing the primary or fallback path.
- Fallback selection remains subject to the same budget and policy validation as the primary path.
- `air_gapped` routing rejects any provider or model not present in the self-hosted catalog.

### Shared Health-State Storage Contract

Shared provider health should be stored outside individual workers.

| State slice | Storage expectation | Reason |
|---|---|---|
| Breaker state | Redis keyspace with provider-scoped state and expiry | Shared source of truth across workers |
| Failure window | Redis sorted-set or equivalent sliding-window structure | Pool-wide threshold evaluation |
| Half-open lease | Redis lease or atomic counter | Bound the number of recovery probes |
| Local cache | Short-lived worker-local cache only | Performance optimization, never source of truth |

Health-state rules:

- State transitions must be auditable through metrics and logs even if Redis is the operational source of truth.
- A provider returning to half-open or healthy must not resume full traffic until the bounded recovery policy permits it.
- Shadow and primary worker pools may share the same provider health view, but metric labels must keep pool behavior inspectable.

### Budget Reservation And Settlement Interfaces

```python
class BudgetContext(BaseModel):
    tenant_id: str
    team_id: str
    run_id: str
    ticket_key: str
    role: str


class BudgetReservation(BaseModel):
    reservation_id: str
    reserved_amount_usd: Decimal
    ticket_cap_remaining_usd: Decimal
    daily_team_cap_remaining_usd: Decimal
    monthly_team_cap_remaining_usd: Decimal


class BudgetLedger(Protocol):
    async def reserve(self, context: BudgetContext, worst_case_cost_usd: Decimal) -> BudgetReservation: ...
    async def settle(self, reservation_id: str, actual_cost_usd: Decimal) -> None: ...
    async def release_orphaned(self, reservation_id: str, reason: str) -> None: ...
```

Budget rules:

- Reservations must atomically update every affected counter or fail as a single unit.
- Worst-case estimation uses the selected model, token ceilings, and provider pricing from the pinned rate-card context.
- Settlement records both estimated and actual cost so refunds and drift can be audited later.
- Orphan recovery must be idempotent and traceable so repeated cleanup does not credit budget twice.

### Model Catalog And Token Cap Contract

The future model catalog should separate provider metadata, model validation, and role policy.

| Catalog field | Purpose |
|---|---|
| `model_id`, `provider_id`, `deployment_profile` | Identify where the model is allowed to run |
| `max_input_tokens`, `max_output_tokens` | Hard technical ceiling |
| `default_price_card_id` | Link budget estimates and billing rollups |
| `supports_tools`, `supports_json_mode`, `supports_streaming` | Capability validation against role needs |
| `allowed_fallback_targets` | Bound legal fallback transitions |

Validation rules:

- Unknown model IDs fail config validation immediately.
- Effective token ceilings are the minimum of model limits, role policy ceilings, and any stricter tenant override.
- `air_gapped` catalogs are explicitly pinned and cannot inherit connected-environment provider IDs.

## Metering And Billing Interfaces

### Usage Recording Schema

Every invocation should produce a stable usage record.

| Field group | Required fields |
|---|---|
| Identity | `usage_id`, `tenant_id`, `team_id`, `run_id`, `ticket_key`, `role` |
| Provider attribution | `provider_id`, `model_id`, `deployment_profile`, `fallback_used` |
| Consumption | `input_tokens`, `output_tokens`, `cached_tokens`, `latency_ms`, `request_count` |
| Budget context | `reservation_id`, `estimated_cost_usd`, `actual_cost_usd`, `rate_card_id` |
| Traceability | `trace_id`, `span_id`, `started_at`, `completed_at`, `status` |

Schema rules:

- Usage records are append-only operational facts.
- Reconciliation and rollups derive from usage records; they do not rewrite the raw records.
- Status must distinguish successful invocation, provider failure, budget rejection, and settlement recovery paths.

### Rollup, Export, And Rate-Card Contracts

| Contract | Baseline rule |
|---|---|
| Hourly rollups | Group by time bucket, tenant, team, role, provider, model, and rate card so closed periods can be reproduced later |
| Export API | Bounded export surfaces provide CSV and optional JSONL without direct finance access to operational tables |
| Rate-card versioning | Every usage record stores the rate-card version active at usage time |
| Invoice evidence | Reconciliation outputs retain links to source usage IDs, rollup IDs, and provider statements |

Export interface sketch:

```python
class MeteringExportRequest(BaseModel):
    tenant_id: str
    period_start: datetime
    period_end: datetime
    format: Literal["csv", "jsonl"]
    sealed_period_only: bool = True
```

### Observability Hooks For LLM Governance

This phase defines the signals that later observability work must expose:

- Provider breaker open and half-open transitions
- Fallback invocation counts and failover saturation
- Budget reservation denials by cap type
- Orphaned reservation recovery counts and age
- Billing reconciliation drift amount and affected period count

These hooks are contract-level requirements now and become concrete metrics, traces, and alerts in phase 7.

## Verification Fixtures

| Task | Fixture definition | Expected proof |
|---|---|---|
| 4.1 Failover validation | Simulate primary outage, bounded half-open recovery, fallback success, then total provider outage and later recovery. | Healthy fallback keeps the run moving; all providers down pauses the run with `all_providers_unavailable`; recovery resumes from the prior checkpoint without losing context. |
| 4.2 Atomic budget validation | Trigger parallel reservations against the same ticket and team caps from multiple workers. | Reservations either succeed atomically within limits or fail together without overspending shared caps. |
| 4.3 Metering reproducibility | Rebuild rollups and exports from raw usage records and compare them with stored rollups and reconciliation output. | Export totals, rate-card application, and drift calculations are reproducible from the recorded usage facts. |

These fixtures connect forward into later phases:

- Phase 5 uses the same catalog and router contracts for graph and agent configuration validation.
- Phase 6 consumes metering exports and failover state in operator surfaces.
- Phase 7 converts the observability hooks above into dashboards, alerts, and CI checks.

## Implementation Slice

This phase now includes a contract-level backend governance slice under `backend/src/backend/governance/` plus test coverage in `backend/tests/test_llm_governance_contracts.py`.

Implemented modules:

- `catalog.py` validates pinned model IDs, deployment-profile compatibility, fallback legality, and effective role-aware token caps.
- `routing.py` models shared provider health, bounded half-open probes, per-role primary and fallback assignments, and explicit failover reasons.
- `budget.py` provides in-memory atomic reservation, settlement, refund, and orphan-release behavior that can be stressed with parallel tests.
- `metering.py` records attributed usage facts, derives reproducible hourly rollups, exports bounded CSV or JSONL payloads, and calculates reconciliation drift against provider totals.

Runtime alignment:

- Phase 1 escalation enums and default sink registration now include the LLM governance reasons introduced by this design.
- The implementation remains synchronous and in-memory so the contracts are executable before Redis, PostgreSQL, or provider SDK coupling is introduced.
- These services are policy primitives only. They do not replace the later distributed implementations for breaker state, ledger durability, or operator-facing billing workflows.
