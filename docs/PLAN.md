# LangGraph Dev Squad

Multi-agent system that resolves Jira tickets by iterating on code until all tests pass, then submits a PR to GitHub. Designed for **self-hosted enterprise deployment** on Kubernetes with multi-tenant isolation (teams/BUs inside a single customer-owned cluster), horizontal scaling, and production-grade observability.

## Deployment Model

- **Self-hosted only** — the system is installed and operated by the customer inside their own infrastructure (on-prem Kubernetes, managed EKS/GKE/AKS, or a dedicated cluster in the customer's cloud account). There is no vendor-operated SaaS control plane.
- **No cross-customer data plane** — every install is a single-tenant deployment at the infrastructure boundary; "multi-tenancy" inside the app refers to isolating teams/BUs/projects owned by the same customer.
- **Customer-owned secrets and data** — Vault, KMS, PostgreSQL, Redis, object storage, and LLM provider accounts all live in the customer's environment. The vendor never has standing access to tenant data.
- **Vendor support access** — support is read-only, time-boxed, and break-glass (dual-control), delivered via the customer's IdP (OIDC) and audited in the customer's `audit_log`.
- **Data residency** — determined entirely by where the customer deploys; LLM provider selection per-tenant allows further regional constraints (EU-only, US-only, air-gapped via self-hosted OpenCode Go).
- **Air-gapped profile** — a constrained variant that pins LLM calls to the customer's self-hosted OpenCode Go and disables Anthropic/OpenAI fallbacks is supported as a documented deployment mode.

## Architecture

```
                     Internet / SaaS Integrations
                             │
                             ▼
                    ┌────────────────┐
                    │  Ingress/NGINX │
                    │  (TLS + rate)  │
                    └───────┬────────┘
                            │
              ┌─────────────▼──────────────┐
              │   Kubernetes Cluster        │
              │                             │
              │  ┌───────────────────────┐  │
              │  │ Frontend Deployment   │  │
              │  │ (2 pods)              │  │
              │  │ - Monitoring UI       │  │
              │  │ - Admin UI            │  │
              │  └───────────────────────┘  │
              │                             │
              │  ┌───────────────────────┐  │
              │  │ API Deployment        │  │
              │  │ (HPA: 2-6 pods)       │  │
              │  │ - Webhooks            │  │
              │  │ - Status/Stream API   │  │
              │  │ - Admin API           │  │
              │  │ - Auth callback       │  │
              │  └──────────┬────────────┘  │
              │             │               │
              │  ┌──────────▼────────────┐  │
              │  │ Redis Cluster         │  │
              │  │ (3 primaries +        │  │
              │  │  3 replicas)          │  │
              │  │ - Queue + pub/sub     │  │
              │  │ - Idempotency         │  │
              │  └──────┬─────────┬──────┘  │
              │         │         │         │
              │  ┌──────▼───┐ ┌──▼───────┐  │
              │  │ Worker   │ │ Shadow   │  │
              │  │ Pool      │ │ Worker   │  │
              │  │ HPA 2-10  │ │ Pool 1-2 │  │
              │  │ LangGraph │ │ readonly │  │
              │  └─────┬─────┘ └────┬────┘  │
              │        │             │       │
              │        └──────┬──────┘       │
              │               ▼              │
              │  ┌───────────────────────┐  │
              │  │ Sandbox Jobs          │  │
              │  │ (per ticket / retry)  │  │
              │  │ gVisor + tenant ns    │  │
              │  └───────────────────────┘  │
              │                             │
              │  ┌───────────────────────┐  │
              │  │ PostgreSQL HA         │  │
              │  │ (1 primary + 1 sync   │  │
              │  │  + 1 async replica)   │  │
              │  │ - Checkpoints         │  │
              │  │ - Memory/config/audit │  │
              │  └───────────────────────┘  │
              │                             │
              │  ┌───────────────────────┐  │
              │  │ Observability Stack   │  │
              │  │ - Prometheus          │  │
              │  │ - Alertmanager        │  │
              │  │ - Grafana             │  │
              │  │ - Loki + Tempo        │  │
              │  └───────────────────────┘  │
              │                             │
              │  ┌───────────────────────┐  │
              │  │ Maintenance CronJobs  │  │
              │  │ - sandbox-cleanup     │  │
              │  │ - retention-cleanup   │  │
              │  │ - status-page-sync    │  │
              │  └───────────────────────┘  │
              └─────────────────────────────┘
                  │        │         │        │
             ┌────▼───┐ ┌──▼────┐ ┌──▼─────┐ ┌▼──────────┐
             │  Jira  │ │ GitHub│ │  OIDC  │ │ LangSmith │
             │  API   │ │  API  │ │Provider│ │  SaaS     │
             └────────┘ └───────┘ └────────┘ └───────────┘
```

`planner`, `coder`, `tester`, `reviewer`, and `pr_creator` are logical roles executed inside `worker` and `worker-shadow` pods; they are not separate Kubernetes workloads. `PgBouncer` runs as a sidecar injected into `api`, `worker`, and `worker-shadow` pods, so it is not counted as a standalone production workload.

## Stack

| Layer | Technology | Purpose |
|---|---|---|
| Orchestration | LangGraph >=1.0,<2.0 | StateGraph, loops, checkpoints |
| LLM | OpenCode Go models by default | Reasoning and code generation, with per-agent model selection |
| LLM Provider | OpenCode Go (`opencode-go/*`) primary + fallback providers | Default provider for all agent roles, with automatic failover |
| LLM Routing | Custom provider router with circuit breakers | Multi-provider failover, health tracking, cost-aware routing |
| State Persistence | langgraph-checkpoint-postgres | Checkpointing, resume from failure |
| Memory | langgraph.store.postgres (PostgresStore) | Long-term memory across threads, namespaced per tenant/repo |
| Vector Search (optional) | pgvector on PostgreSQL | Semantic retrieval for internal docs, enterprise patterns, and local technical knowledge |
| Prebuilt Agents | langgraph.prebuilt (create_react_agent) | Agent and tool execution |
| Sandbox | Kubernetes Jobs + gVisor (runsc) runtime | Hardened isolated code execution with resource limits |
| Jira | jira (Python) >=3.8 | Jira API client |
| GitHub | PyGithub >=2.4 | GitHub API client |
| Git | gitpython >=3.1 | Git operations |
| Observability | langsmith >=0.2 + Prometheus + Alertmanager + Grafana + Loki + Tempo | Tracing, metrics, logs, dashboards, alerting |
| API | FastAPI >=0.115 | Webhook receiver, status API, admin API |
| Queue | ARQ >=0.26 | Async Redis queue with dead letter queue |
| Auth | authlib + OIDC provider | SSO/OIDC authentication, RBAC, HMAC webhook verification |
| DB | PostgreSQL >=16 (HA) | Checkpoints, memory, config, metering, audit |
| Cache | Redis >=7 (Cluster) | ARQ queue, SSE pub/sub, idempotency, rate limiting |
| Container Runtime | Kubernetes >=1.30 + gVisor | Orchestration, pod scheduling, sandbox isolation |
| Infra-as-Code | Helm charts + Kustomize | Declarative Kubernetes deployment |
| Frontend | Vite + React + TypeScript | Monitoring + administration in a single app |
| Secrets | HashiCorp Vault + External Secrets Operator | Envelope encryption, key rotation, DEK/KEK separation |
| Connection pool | PgBouncer (transaction mode) | Postgres connection multiplexing, read replica routing |
| Rate limiting | Redis + slowapi (FastAPI) + NGINX ingress | Per-tenant, per-IP, per-endpoint quotas |
| API gateway | NGINX ingress (edge) + FastAPI middleware | TLS, WAF hooks, rate limits, IP allowlists |
| Feature flags | OpenFeature SDK + Unleash (self-hosted) or LaunchDarkly | Gradual rollout, kill switches, per-tenant variants |
| Tracing | OpenTelemetry SDK + OTLP → Tempo + LangSmith | End-to-end distributed traces (W3C Trace Context) |
| Supply chain | syft (SBOM) + cosign (signing) + SLSA provenance + Renovate | Supply chain integrity, reproducibility, auto-patching |
| Dep scanning | Trivy + Grype + OSV-Scanner + FOSSA/ScanCode | Vulnerability + license compliance in CI |
| Secret scanning | gitleaks + trufflehog (pre-commit + CI + diff guard) | Prevent leaked credentials in repos, PRs, logs |
| Backup | pgBackRest or Barman + Velero (K8s) | PITR for Postgres, disaster recovery snapshots |
| Status page | Statuspage.io or Atlassian Statuspage (embedded) | Public incident comms, component health |

## Model Assignment

| Agent | Primary Model | Fallback Model | Rationale |
|---|---|---|---|
| Planner | `opencode-go/glm-5` | `anthropic/claude-opus-4-7` | Highest default reasoning depth for architecture, planning, and ambiguity reduction |
| Coder | `opencode-go/kimi-k2.5` | `anthropic/claude-sonnet-4-6` | Strong coding/tool-calling default with better cost/latency balance for iterative implementation |
| Tester | `opencode-go/minimax-m2.7` | `anthropic/claude-haiku-4-5-20251001` | Lower-cost, fast default for repeated test/result interpretation loops |
| Reviewer | `opencode-go/glm-5` | `anthropic/claude-sonnet-4-6` | Strong default analytical model for plan/code comparison and structured review output |
| PR Creator | `opencode-go/minimax-m2.5` | `anthropic/claude-haiku-4-5-20251001` | Fast, economical default for release coordination, PR text synthesis, and Jira updates |

These are the default model assignments only. Agent configs can override the model per role through the admin UI or persisted config. OpenCode model IDs must use the `opencode-go/<model-id>` format documented by OpenCode Go and are resolved against a pinned model catalogue at deploy time — unknown IDs fail config validation rather than silently falling back. Fallback models activate automatically when the primary provider circuit breaker trips. For the air-gapped deployment profile, fallbacks are pinned to additional self-hosted OpenCode Go models instead of Anthropic/OpenAI.

### LLM Provider Routing & Circuit Breakers

```python
class ProviderHealth(BaseModel):
    provider: str                      # "opencode-go", "anthropic", "openai"
    status: Literal["healthy", "degraded", "open"]
    failure_count: int = 0
    last_failure: datetime | None = None
    circuit_open_until: datetime | None = None
    success_rate_1h: float = 1.0       # rolling 1-hour success rate

class ProviderRouter:
    """Routes LLM requests with automatic failover and health tracking."""

    # Circuit breaker thresholds (pool-wide, enforced via Redis)
    FAILURE_THRESHOLD: int = 10         # pool-wide failures within FAILURE_WINDOW trip the breaker
    FAILURE_WINDOW: timedelta = timedelta(minutes=1)
    RECOVERY_WINDOW: timedelta = timedelta(minutes=5)
    HALF_OPEN_REQUESTS: int = 2         # test requests during recovery, coordinated via Redis lease

    async def route(
        self,
        role: str,
        agent_config: AgentConfig,
        budget: "BudgetContext",
    ) -> tuple[str, str]:
        """Returns (provider, model) after checking pool-wide health + budget."""
        primary = agent_config.model
        provider = self._extract_provider(primary)

        if await self._is_healthy(provider):
            if await self._reserve_budget(budget, role, provider):
                return provider, primary
            raise BudgetExhaustedError(budget.tenant_id, role)

        fallback = agent_config.fallback_model
        if fallback:
            fb_provider = self._extract_provider(fallback)
            if await self._is_healthy(fb_provider):
                if await self._reserve_budget(budget, role, fb_provider):
                    self._emit_metric("provider_failover", provider=provider, fallback=fb_provider)
                    return fb_provider, fallback

        raise AllProvidersUnavailableError(role, [provider])
```

**Shared circuit breaker (Redis-coordinated)** — A naive per-worker breaker wastes capacity during an outage: with 2–10 workers each burning `FAILURE_THRESHOLD` calls before tripping, the pool can collectively send 50+ doomed requests while every worker independently learns the provider is down. Breaker state is therefore coordinated across the pool:

```python
# Keys (all per provider):
#   cb:{provider}:state       → "closed" | "open" | "half_open"
#   cb:{provider}:failures    → sliding-window ZSET of failure timestamps
#   cb:{provider}:open_until  → unix ts until which the breaker stays open
#   cb:{provider}:half_lease  → SET NX lease granting HALF_OPEN probe slots

async def record_failure(provider: str) -> None:
    now = time.time()
    cutoff = now - FAILURE_WINDOW.total_seconds()
    async with redis.pipeline(transaction=True) as p:
        p.zremrangebyscore(f"cb:{provider}:failures", 0, cutoff)
        p.zadd(f"cb:{provider}:failures", {str(uuid4()): now})
        p.zcard(f"cb:{provider}:failures")
        _, _, count = await p.execute()
    if count >= FAILURE_THRESHOLD:
        await redis.set(f"cb:{provider}:state", "open", ex=int(RECOVERY_WINDOW.total_seconds()))
        await redis.set(f"cb:{provider}:open_until", now + RECOVERY_WINDOW.total_seconds())

async def is_healthy(provider: str) -> bool:
    state = await redis.get(f"cb:{provider}:state") or b"closed"
    if state == b"closed":
        return True
    if state == b"open":
        open_until = float(await redis.get(f"cb:{provider}:open_until") or 0)
        if time.time() < open_until:
            return False
        # Attempt to transition to half_open with a Redis lease (only HALF_OPEN_REQUESTS probes allowed)
        granted = await redis.set(f"cb:{provider}:half_lease", "1", nx=True, ex=30)
        if granted:
            await redis.set(f"cb:{provider}:state", "half_open", ex=60)
            return True
        return False
    if state == b"half_open":
        # Limit concurrent probes via an atomic counter
        count = await redis.incr(f"cb:{provider}:probes")
        await redis.expire(f"cb:{provider}:probes", 60)
        return count <= HALF_OPEN_REQUESTS
    return False
```

Local in-memory caching of breaker state (100ms TTL) is acceptable to avoid Redis on every call, but the source of truth is Redis. Each worker scrapes its local view as a Prometheus gauge (`devsquad_provider_breaker_local`) separately from the shared state (`devsquad_provider_breaker_shared`) so operators can spot drift. Every LLM invocation must carry a full `BudgetContext` so routing decisions can enforce per-ticket and per-team caps before a provider is selected.

**All-providers-down behaviour.** When every configured provider breaker is open, the router raises `AllProvidersUnavailableError`. The node wrapper catches it and:

1. Checkpoints the current state and marks the run `paused_at_node` with `escalation_reason="all_providers_unavailable"` — the run is **paused**, not failed, so it can resume automatically once a breaker closes.
2. Emits the `AllProvidersDown` Prometheus alert (see Alerting Rules).
3. Posts a Jira comment linking the run and the status page.
4. A periodic re-dispatcher checks every 60s whether any provider has recovered; on recovery it resumes paused runs in FIFO order within each tenant's fair-queue slot.
5. Chaos test `test_all_providers_unavailable` validates: primary + fallback both hard-down → run pauses (not fails) → recovery restores one provider → run resumes from last checkpoint → succeeds. Runbook: `docs/runbooks/all-providers-down.md`.

## LLM Economics & Budget Governance

### Cost Model

| Item | Baseline | With Retries (avg 2x) | Pathological (max retries) |
|---|---|---|---|
| Single ticket | $1-3 | $3-8 | $15-25 |
| Daily (10 tickets) | $10-30 | $30-80 | $150-250 |
| Monthly (200 tickets) | $200-600 | $600-1,600 | $3,000-5,000 |

### Budget Enforcement

```python
class BudgetContext(BaseModel):
    tenant_id: str
    team_id: str
    ticket_key: str
    max_cost_per_ticket: Decimal
    remaining_ticket_budget_usd: Decimal
    remaining_team_daily_budget_usd: Decimal
    remaining_team_monthly_budget_usd: Decimal

class BudgetConfig(BaseModel):
    """Hierarchical budget caps enforced at the metering layer."""
    max_cost_per_ticket: Decimal = Decimal("25.00")       # hard cap per ticket run
    max_cost_per_team_daily: Decimal = Decimal("200.00")  # hard daily cap per team
    max_cost_per_team_monthly: Decimal = Decimal("5000.00")
    alert_threshold_pct: int = 80                          # alert when 80% consumed

    # max_tokens_per_agent_call is NOT a single global number: it is derived
    # per-role and per-model from the pinned model catalogue, then clamped by
    # the tenant/team override if present. See MODEL_TOKEN_CAPS below.

class TokenMeter:
    """Records every LLM invocation with full attribution."""

    async def record(
        self,
        tenant_id: str,
        team_id: str,
        ticket_key: str,
        agent_role: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
        latency_ms: int,
        trace_id: str,
    ) -> None:
        """Insert into metering table and settle the reservation for this call."""
        ...

    async def check_budget(
        self,
        tenant_id: str,
        team_id: str,
        ticket_key: str | None = None,
    ) -> BudgetStatus:
        """Returns remaining budget at ticket, daily, and monthly levels."""
        ...
```

**Atomic budget reservation (avoids check-then-act race)** — A naive "check budget → call LLM → record cost" flow allows multiple concurrent nodes in the same ticket, or multiple workers on different tickets for the same team, to all pass the check simultaneously and collectively exceed the cap. Budgets are enforced via an atomic Redis reservation pattern:

```python
# Keys:
#   budget:ticket:{run_id}   → remaining cents for this run
#   budget:team:daily:{team_id}:{yyyymmdd}
#   budget:team:monthly:{team_id}:{yyyymm}

async def reserve(
    tenant_id: str, team_id: str, run_id: str,
    role: str, provider: str, model: str,
    estimated_input_tokens: int, max_output_tokens: int,
) -> str:
    """Atomically decrement all three budget counters by the estimated cost.

    Returns a reservation_id that must be settled by record() with actual cost.
    Raises BudgetExhaustedError if any counter would go negative.
    """
    estimated_cents = estimate_cost_cents(
        provider, model, estimated_input_tokens, max_output_tokens,
        # rate card — use worst-case output to avoid under-reservation
    )
    reservation_id = str(uuid4())

    # Lua script: DECR all three keys in one round trip; rollback all if any underflows
    script = """
    local run = redis.call('DECRBY', KEYS[1], ARGV[1])
    local daily = redis.call('DECRBY', KEYS[2], ARGV[1])
    local monthly = redis.call('DECRBY', KEYS[3], ARGV[1])
    if run < 0 or daily < 0 or monthly < 0 then
      redis.call('INCRBY', KEYS[1], ARGV[1])
      redis.call('INCRBY', KEYS[2], ARGV[1])
      redis.call('INCRBY', KEYS[3], ARGV[1])
      return -1
    end
    redis.call('HSET', KEYS[4], 'reserved', ARGV[1], 'role', ARGV[2])
    redis.call('EXPIRE', KEYS[4], 900)  -- 15 min to settle
    return 1
    """
    ok = await redis.eval(
        script, 4,
        f"budget:ticket:{run_id}",
        f"budget:team:daily:{team_id}:{today}",
        f"budget:team:monthly:{team_id}:{month}",
        f"budget:reservation:{reservation_id}",
        estimated_cents, role,
    )
    if ok == -1:
        raise BudgetExhaustedError(tenant_id, role)
    return reservation_id

async def settle(reservation_id: str, actual_cost_cents: int) -> None:
    """Reconcile the reservation with the measured cost after the LLM call.

    - If actual < estimated: credit the delta back to all three counters.
    - If actual > estimated: debit the delta (cannot underflow because the run
      already paid the worst-case estimate).
    - Always insert the llm_usage row and delete the reservation key.
    """
    ...

async def reconcile_expired_reservations() -> None:
    """Background job: any reservation older than 15 min with no matching
    llm_usage row is assumed to have failed mid-call. Credit the reserved
    amount back and emit a `budget_reservation_orphaned` metric."""
    ...
```

Budget counters are seeded at run start from PostgreSQL (`max_cost_per_ticket`, team caps minus any usage already recorded in the current day/month). Seeding is idempotent via `SET NX`. Every LLM call path must `reserve()` before the call and `settle()` in a `finally` — the DLQ handler settles with `actual_cost=0` on unrecoverable errors. Because the reservation uses the **worst-case** estimated cost, concurrent nodes cannot collectively exceed the cap; at worst they under-utilise it and receive a refund at settle time.

### Metering Database Schema

```sql
CREATE TABLE llm_usage (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    team_id         TEXT NOT NULL,
    ticket_key      TEXT NOT NULL,
    agent_role      TEXT NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    cost_usd        NUMERIC(10, 6) NOT NULL,
    latency_ms      INTEGER NOT NULL,
    trace_id        TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Partition by month for retention management
    CONSTRAINT llm_usage_created_at_check CHECK (created_at IS NOT NULL)
) PARTITION BY RANGE (created_at);

-- Indexes for budget queries
CREATE INDEX idx_llm_usage_tenant_daily ON llm_usage (tenant_id, team_id, created_at);
CREATE INDEX idx_llm_usage_ticket ON llm_usage (ticket_key, created_at);

-- Materialized view for dashboard cost reporting
CREATE MATERIALIZED VIEW daily_cost_summary AS
SELECT
    tenant_id, team_id, agent_role, provider, model,
    DATE(created_at) AS day,
    SUM(cost_usd) AS total_cost,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    COUNT(*) AS invocation_count,
    AVG(latency_ms) AS avg_latency_ms
FROM llm_usage
GROUP BY tenant_id, team_id, agent_role, provider, model, DATE(created_at);
```

Budget checks run before every LLM invocation. When a ticket exceeds its cap, the system escalates to human with `escalation_reason = "budget_exhausted"` rather than silently continuing.

### Billing & Metering Export

Metering is the source of truth for both budget enforcement and customer billing. A separate export pipeline prevents the billing system from querying the operational database directly.

- **Hourly rollup** — A scheduled job aggregates `llm_usage` into `billing_rollup_hourly` by (tenant_id, team_id, agent_role, model, hour). Rows are marked `sealed=true` once the hour closes to make billing calculations reproducible.
- **Usage export API** — `GET /api/metering/export?tenant_id=...&from=...&to=...&format=csv|jsonl` (super_admin) for finance/ERP ingestion. Export requests are rate-limited and audited.
- **Billing connector contract** — The plan commits to a stable schema the billing system can consume (Stripe metered billing, NetSuite, or custom ERP). Schema changes are backwards-compatible within a major version.
- **Rate card versioning** — `price_rate_cards` table stores per-provider/model `$/1K input tokens` and `$/1K output tokens` with `effective_from`/`effective_to`. Historical invoices re-compute against the rate card active at usage time.
- **Reconciliation** — A nightly job compares `SUM(cost_usd) from llm_usage` against provider invoice totals (Anthropic, OpenAI, OpenCode) and alerts on drift > 2%.
- **Invoice dispute evidence** — Each `llm_usage` row carries `provider_request_id` for cross-reference with provider usage logs.

```sql
CREATE TABLE billing_rollup_hourly (
    tenant_id      TEXT NOT NULL,
    team_id        TEXT NOT NULL,
    agent_role     TEXT NOT NULL,
    provider       TEXT NOT NULL,
    model          TEXT NOT NULL,
    hour_bucket    TIMESTAMPTZ NOT NULL,
    input_tokens   BIGINT NOT NULL,
    output_tokens  BIGINT NOT NULL,
    cost_usd       NUMERIC(14, 6) NOT NULL,
    invocations    INTEGER NOT NULL,
    sealed         BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (tenant_id, team_id, agent_role, provider, model, hour_bucket)
);

CREATE TABLE price_rate_cards (
    provider             TEXT NOT NULL,
    model                TEXT NOT NULL,
    input_per_1k_usd     NUMERIC(10, 6) NOT NULL,
    output_per_1k_usd    NUMERIC(10, 6) NOT NULL,
    effective_from       TIMESTAMPTZ NOT NULL,
    effective_to         TIMESTAMPTZ,
    PRIMARY KEY (provider, model, effective_from)
);
```

## Multi-Tenancy & Isolation

### Tenant Model

Each tenant represents an organization or business unit. Tenants own teams, which own repositories and credentials.

```python
class Tenant(BaseModel):
    id: str                                # UUID
    name: str                              # "Platform Engineering"
    oidc_org_id: str                       # maps to IdP organization
    budget_config: BudgetConfig
    allowed_repos: list[str]               # ["org/repo-a", "org/repo-b"]
    created_at: datetime
    updated_at: datetime

class Team(BaseModel):
    id: str
    tenant_id: str
    name: str                              # "Backend Team"
    members: list[str]                     # OIDC subject IDs
    repos: list[str]                       # subset of tenant.allowed_repos
    jira_project_keys: list[str]           # ["BACK", "INFRA"]
    credential_set_id: str                 # references isolated credentials
    daily_budget_override: Decimal | None  # optional team-level override
```

### Credential Isolation

```python
class CredentialSet(BaseModel):
    """Per-team credential set. Envelope-encrypted at rest in PostgreSQL."""
    id: str
    tenant_id: str
    team_id: str
    # Ciphertext encrypted with a per-tenant Data Encryption Key (DEK).
    # The DEK is wrapped by a tenant-scoped Key Encryption Key (KEK) in KMS/Vault.
    github_token_ciphertext: bytes
    jira_token_ciphertext: bytes
    dek_id: str                            # reference to wrapped DEK version
    github_app_installation_id: str | None # MANDATORY for v1 — PAT is fallback only
    created_at: datetime
    rotated_at: datetime                   # track rotation compliance
    next_rotation_due: datetime            # enforced 90-day rotation SLA

    # Credentials are NEVER passed to the LLM context.
    # They are resolved at the service layer by the sandbox/tool
    # using the tenant_id + team_id from TicketState.
```

#### GitHub App enforcement (v1)

- **GitHub App is the default path.** Tenants onboard via an org-scoped GitHub App install that grants least-privilege permissions (`contents: write`, `pull_requests: write`, `checks: read`, `metadata: read`).
- **PAT is explicit opt-in only** — fallback for environments where App installation is impossible. PAT-based tenants are flagged in the admin UI and get stricter rate limits + extra audit events.
- **Installation tokens are minted on demand** (1h TTL) through the App JWT flow; no long-lived PATs are stored.
- **Scopes are validated before every tool call** — PR Creator refuses to push to `main`, `release/*`, and any branch protected by a server-side rule.

#### Envelope encryption & key management

- **Vault standard** — HashiCorp Vault is the system of record for runtime secrets, tenant credentials, and wrapped DEK references. External Secrets Operator (ESO) is the only supported sync path into Kubernetes-native Secrets for v1.
- **Production topology** — Production uses an external Vault control plane by default (HCP Vault Dedicated or self-managed Vault HA with integrated Raft). Vault is intentionally kept outside the application workload inventory so a compromise or restart of the app cluster does not also take down the secret authority.
- **Kubernetes auth in prod** — ESO authenticates to Vault through the Kubernetes auth method using a `ClusterSecretStore`; static Vault tokens are not used in production workloads.
- **Local bootstrap only** — `local-minikube` may use Vault dev mode and a bootstrap token for convenience, but that path is explicitly non-production.
- **KEK** — tenant-scoped, stored in KMS/Vault, never leaves the HSM boundary. Rotated every 12 months with staged re-wrap.
- **DEK** — per-tenant, symmetric AES-256-GCM; wrapped by KEK and cached in memory with 15-minute TTL at the service layer.
- **Rotation SLA** — tenant credentials must be rotated within 90 days (`next_rotation_due`). Expired rotation triggers a `credential_rotation_overdue` alert and blocks new runs for that tenant.
- **Secret delivery** — ESO syncs secret material and KEK references from Vault into Kubernetes Secrets; no plaintext secrets in Helm values, ConfigMaps, or long-lived container env.
- **Break-glass** — a dual-control emergency access path (two super_admins) is required to view or force-rotate any credential; every break-glass event is auditable.

### Isolation Boundaries

| Boundary | Mechanism | Enforced At |
|---|---|---|
| Repo access | Team-scoped `allowed_repos` | Webhook intake + sandbox clone |
| Credentials | Per-team encrypted credential sets | Service layer (never in LLM context) |
| Memory | Namespace `(tenant_id, repo, ticket_key)` | PostgresStore namespace |
| Budget | Per-ticket + per-team hard caps | TokenMeter + ProviderRouter pre-invocation check |
| Visibility | Tenant/team scoping on all queries | API middleware + DB row-level |
| Queue priority | Per-tenant queue weight | ARQ job metadata |
| Sandbox | Dedicated Kubernetes namespace per tenant | NetworkPolicy + ResourceQuota |

### Data Visibility Rules

- Authenticated users see only jobs/tickets belonging to their tenant and team(s).
- Admin users see all jobs within their tenant; they cannot see other tenants.
- Super-admin users (platform operators) see all tenants for operational purposes.
- SSE streams are scoped by tenant_id + team_id; a subscription cannot leak cross-tenant events.

## Context Retrieval Policy

Before any agent uses external search or third-party documentation, it must resolve context in this order:

1. **Jira-first** — Ticket payload, summary, description, comments, and linked metadata from the incoming webhook.
2. **Repo-first** — Local repository contents, relevant source files, tests, config, and git metadata for the target branch.
3. **Run-state and memory** — Existing checkpointed graph state plus namespaced long-term memory for the repository/ticket.
4. **Optional internal knowledge base** — Feature-flagged pgvector retrieval over tenant-scoped enterprise patterns, runbooks, and local technical documentation when the ticket requires prior organizational knowledge not already present in repo state.
5. **First-party APIs** — GitHub/Jira API lookups for branch, PR, commit, and issue metadata that is not already local.
6. **External research last** — External docs/web search only when the previous five layers do not provide enough information to complete the step reliably.

This policy applies especially to the planner and reviewer. External research is allowed, but it is a fallback path rather than the default source of truth.

### Optional Internal Knowledge Retrieval (`pgvector`)

The system may expose a feature-flagged internal RAG layer backed by `pgvector` in the same production PostgreSQL cluster already used for checkpoints, memory, and config. This is optional and disabled by default for v1 tenants, but the architecture should support enabling it without introducing a separate vector database.

- **Primary use cases** — enterprise patterns, internal runbooks, architecture decision records, local technical documentation, approved API references, and tenant-provided implementation guidance.
- **No extra datastore** — embeddings and chunk metadata live in PostgreSQL with `pgvector`; no Chroma/OpenSearch dependency is introduced for v1.
- **Read path** — retrieval is tenant-scoped and filtered by `knowledge_base`, `source_type`, `repo_full_name`, `visibility_scope`, and optional version tags before nearest-neighbor ranking.
- **Index strategy** — default to `HNSW` on cosine distance for production retrieval quality; `IVFFlat` is an optional tuning path for very large corpora or controlled rebuild windows.
- **Role policy** — `planner` and `reviewer` may query the knowledge base by default when the feature flag is enabled; `coder` can be granted read-only access for implementation-time lookups, but remains unable to mutate knowledge content.
- **State persistence** — retrieved excerpts are summarized and persisted in graph state so retries and reviews operate on the same retrieved context instead of re-querying blindly.
- **Write path** — ingestion is asynchronous and admin-controlled. Agents never write directly to the knowledge base during ticket execution.

## Tool Invocation Preference

When the system interacts with developer platforms, cloud services, or delivery infrastructure, it should prefer official CLIs and native command surfaces before MCP integrations.

- **CLI-first by default** — Prefer stable operational CLIs such as `git`, `gh`, `aws`, `gcloud`, `kubectl`, `helm`, `terraform`, and provider-specific build/package tools before introducing MCP adapters.
- **Why CLI-first** — CLIs match the workflows operators already use, are easier to audit and replay, reduce hidden adapter state, and keep failure modes closer to real production behavior.
- **MCP as fallback** — MCP integrations are allowed only when an official CLI does not exist, does not expose the required capability, or the MCP tool provides a materially safer read-only surface than shelling out.
- **Service-layer wrapping** — Agents should invoke backend/service-layer tools that wrap these CLIs or SDKs. Raw MCP access is not the primary execution path for v1.
- **Read-before-write still applies** — CLI preference does not bypass repo-first and first-party context rules. The system still resolves local and first-party context before taking external actions.

## Agent Tool Access Policy

Each agent gets the minimum tool surface needed for its role. The admin UI can configure tools only within the role whitelist below; configs that exceed the whitelist are rejected.

| Agent | Allowed Tool Families | Explicit Boundaries |
|---|---|---|
| Planner | Jira read, repo read, git diff/read, memory read, knowledge-base read, docs/web research | No repo writes, no sandbox execution, no PR creation |
| Coder | Repo read/write, sandbox execution, tests, git local operations, optional knowledge-base read | No Jira write, no GitHub PR creation, no unrestricted external research by default |
| Tester | Repo read, sandbox test execution, diff/read, result summarization | No repo writes, no PR creation, no Jira write |
| Reviewer | Repo read, plan read, diff/read, test result read, knowledge-base read, structured evaluation | No repo writes, no sandbox execution, no PR creation |
| PR Creator | Git branch/commit/push, GitHub PR actions, Jira status/comment updates, PR body/title synthesis | No sandbox execution, no source editing except release metadata and final git operations |

The role whitelist is part of v1 validation and must be enforced both in backend config validation and in the admin UI.

## Autonomous Specification-Driven Workflow

The default execution model for v1 is **autonomous-first Spec-Driven Development** using a Spec Kit-style artifact lifecycle, but orchestrated inside LangGraph rather than through human-driven slash commands. The existing planner/reviewer/coder roles remain, but the planner now owns constitution loading/synthesis, feature specification, ambiguity reduction, implementation planning, and task generation before any repo write happens.

- **Artifact chain** — `constitution -> feature_spec -> clarification_notes -> implementation_plan -> task_list -> implement -> test -> review -> pre_pr_sync -> pr_creator`
- **Repo-write gate** — No repo-writing node may run until `spec_ready_for_implementation=True` and a task list exists in `TicketState`.
- **Autonomous clarify loop** — Ambiguities are resolved first from Jira, repo state, checkpoints, memory, and first-party docs. Human input is not part of the normal success path.
- **Break-glass interrupts only** — Operator approval remains supported for `security_review`, `budget_exhausted`, merge conflicts, policy violations, or unresolved ambiguity after max autonomous spec iterations. A successful ticket should not pause for manual approval.
- **Auditable artifacts** — Constitution, spec, clarification log, plan, and tasks are persisted in state/checkpoints so retries, reviews, and resumes work against the same pinned artifacts.

## Flow

```
 1. Jira webhook hits /webhooks/jira (HMAC signature validated)
 2. Idempotency check: SHA-256(webhook_id + ticket_key + event_type) looked up in Redis
    - If present → deduplicate, return 200 immediately
    - If absent → store key with 24h TTL, continue
 3. Tenant resolution: extract Jira project key → resolve tenant_id + team_id + credential_set
 4. Budget pre-check: verify ticket/team budget is still available for a new run
 5. FastAPI creates `run_id = uuid4()` and persists an execution record + pinned config snapshot
 6. FastAPI enqueues to ARQ with job metadata (run_id, tenant_id, team_id, ticket_key, priority, config_snapshot_id)
 7. ARQ worker picks up job, resolves credentials from CredentialSet, and loads the pinned config snapshot
 8. LangGraph starts with `thread_id = f"{tenant_id}:{ticket_key}:{run_id}"`
 9. Planner resolves context via Jira → repo → memory → optional pgvector knowledge base → first-party APIs → external research fallback
10. Planner loads tenant/repo constitution baseline and derives ticket-scoped constraints
11. Planner writes `feature_spec` with requirements, acceptance criteria, edge cases, and non-goals
12. Reviewer/analyzer checks artifact quality for ambiguity, coverage, and constitution compliance
13. If ambiguity remains and spec_iteration_count < max_spec_iterations → back to Planner for autonomous clarification/rewrite
14. If ambiguity remains and spec_iteration_count >= max_spec_iterations → Escalate to human with unresolved questions
15. Planner creates implementation plan and ordered task list with explicit test expectations
16. Base branch sync: rebase work_branch on latest base_branch, detect merge conflicts
    - If conflicts detected → escalate to human with conflict details
17. Coder implements changes in hardened Kubernetes sandbox strictly against constitution/spec/plan/tasks artifacts
18. Diff size guard: if total diff exceeds MAX_DIFF_LINES (2000), split or escalate
19. Tester runs tests in sandbox (exit code determines pass/fail)
20. If tests fail and test_retry_count < max_test_retries → back to Coder
21. If tests fail and test_retry_count >= max_test_retries → Escalate to human
22. If tests pass → Reviewer checks code against constitution, spec, plan, tasks, and repo/diff/test context
23. If reviewer detects spec drift or missing task decomposition and spec_iteration_count < max_spec_iterations → back to Planner for replan
24. If reviewer rejects implementation and review_retry_count < max_review_retries → back to Coder
25. If review cannot be resolved within spec/review retry limits → Escalate to human
26. If review approves → final base branch sync check for conflicts
27. If conflicts → escalate; if clean → Create branch, commit, push, create PR
28. Update Jira with PR link or escalation note/status
29. Record final cost/token metrics to metering table
30. Checkpoint at every node → resume from any point on failure against the same pinned config snapshot
31. Budget check at every LLM invocation → escalate if budget exhausted
```

## State

`BudgetContext` is defined once under **LLM Economics & Budget Governance** and imported here. The state type does not redefine it.

```python
from .llm.budget import BudgetContext


class TicketState(TypedDict):
    # Run identity / execution pinning
    run_id: str
    thread_id: str
    config_snapshot_id: str
    graph_config_id: str
    graph_config_version: int
    compatibility_epoch: int
    agent_config_versions: dict[str, int]

    # Tenant context
    tenant_id: str
    team_id: str
    credential_set_id: str

    # Ticket
    ticket_id: str
    ticket_key: str
    ticket_summary: str
    ticket_description: str
    ticket_url: str
    jira_project_key: str

    # Repo
    repo_url: str
    repo_full_name: str
    base_branch: str
    work_branch: str

    # SDD artifacts
    autonomy_mode: Literal["autonomous_first"]
    project_constitution: str
    feature_spec: str
    clarification_notes: str
    plan: str                              # implementation plan
    task_list: str
    artifact_analysis: str                 # ambiguity / coverage / constitution checks
    spec_ready_for_implementation: bool
    needs_replan: bool
    repo_context_summary: str
    jira_context_summary: str
    knowledge_context_summary: str         # summarized pgvector retrieval results, if enabled
    knowledge_hits: list[dict]             # source refs / metadata for retrieved internal knowledge
    research_notes: str

    # Code — deduplicated set instead of append-only list
    files_changed: Annotated[set[str], _merge_sets]
    diff_summary: str
    diff_line_count: int                   # guard against oversized diffs

    # Tests
    test_results: str
    tests_passed: bool
    test_output: str
    last_sandbox_exit_code: int            # 0 = pass

    # Review
    review_approved: bool
    review_feedback: str
    review_findings: str

    # Merge conflict detection
    merge_conflict_detected: bool
    merge_conflict_files: list[str]
    base_branch_head_at_start: str         # commit SHA for drift detection
    base_branch_head_current: str

    # Interrupts / approvals
    approval_pending: bool
    approval_target: str                   # node or operation awaiting approval
    approval_payload: dict
    approval_decision: str                 # "approved", "denied", "pending"
    paused_at_node: str

    # Retry
    spec_iteration_count: int
    max_spec_iterations: int
    test_retry_count: int
    max_test_retries: int
    review_retry_count: int
    max_review_retries: int

    # PR
    pr_url: str
    pr_number: int

    # Escalation
    escalated: bool
    escalation_reason: str

    # Cost tracking
    budget_context: BudgetContext
    accumulated_cost_usd: Decimal
    budget_remaining_usd: Decimal
    total_input_tokens: int
    total_output_tokens: int

    # Tracing
    trace_id: str                          # correlation ID across all operations
    span_ids: dict[str, str]               # node_id -> span_id for distributed tracing

    # Messages
    messages: Annotated[list, add_messages]


def _merge_sets(left: set[str], right: set[str]) -> set[str]:
    """Custom reducer that merges file sets without duplicates."""
    return left | right
```

## Graph Structure

```python
def compile_workflow_from_config(
    graph_config: GraphConfig,
    checkpointer: PostgresSaver,
    store: PostgresStore,
) -> CompiledStateGraph:
    validate_graph_invariants(graph_config)
    workflow = StateGraph(TicketState)

    for node in graph_config.nodes:
        workflow.add_node(node.id, resolve_node_handler(node.handler))

    for edge in graph_config.edges:
        if edge.kind == "direct":
            workflow.add_edge(edge.source, edge.target)
        else:
            workflow.add_conditional_edges(
                edge.source,
                resolve_router(edge.router),
                edge.routes,
            )

    if graph_config.interrupt_before:
        return workflow.compile(
            checkpointer=checkpointer,
            store=store,
            interrupt_before=graph_config.interrupt_before,
        )

    return workflow.compile(
        checkpointer=checkpointer,
        store=store,
    )
```

The default graph still starts from the planner-owned SDD artifact phase (`constitution -> feature_spec -> clarify -> plan -> tasks`) before entering coder/tester/reviewer/pr-creator, but in v1 the runtime graph is config-driven, editable from the admin UI, and recompiled from persisted node/edge definitions rather than being hard-coded as the only allowed topology.

`PostgresStore` is not optional in the production runtime: the orchestrator must compile the graph with both `checkpointer` and `store` so planner/reviewer nodes can use persisted memory, SDD artifacts, and context retrieval policies without reconstructing state manually.

### Graph Configuration Schema

```python
class NodeConfig(BaseModel):
    id: str
    kind: Literal["agent", "system"]
    handler: str                  # must resolve from a backend registry
    role: str                     # "planner", "coder", "tester", "reviewer", "pr_creator", etc.
    capabilities: set[str] = set()  # semantic tags used by invariant validation
    version: int = 1              # config version for audit trail

class EdgeConfig(BaseModel):
    source: str
    kind: Literal["direct", "conditional"]
    target: str | None = None
    router: str | None = None     # backend-registered router function
    routes: dict[str, str] = {}   # router output -> node id

class GraphConfig(BaseModel):
    id: str                       # UUID for this config version
    nodes: list[NodeConfig]
    edges: list[EdgeConfig]
    interrupt_before: list[str] = []
    workflow_profile: Literal["ticket_to_pr_v1"] = "ticket_to_pr_v1"
    compatibility_epoch: int = 1  # bump only for breaking resume semantics
    version: int                  # monotonically increasing
    created_by: str               # OIDC subject of admin who saved this
    created_at: datetime
    active: bool = False          # only one config can be active at a time
```

Validation rules for v1 graph editing:

- node handlers and routers must come from a fixed backend registry; the UI cannot submit arbitrary Python
- every graph must define a single entry path from `START` and at least one terminal path to `END`
- loops are allowed only through explicit conditional routes
- every conditional edge must declare a finite route map
- interrupt points are stored as node IDs and compiled via `interrupt_before`
- active configs must satisfy protected v1 workflow invariants, not just topological validity
- any graph containing repo-write handlers must include an SDD readiness guard before the first repo-writing node
- every path that can reach PR creation must also traverse test execution, diff guard, review approval, and pre-PR sync
- any graph containing repo-write handlers must contain at least one planner path that can produce/update SDD artifacts, one tester path, one reviewer path, and one escalation sink
- `pr_creator` is reachable only from a registered pre-PR sync node; direct jumps from coder/tester/reviewer are invalid
- every terminal failure branch must resolve to a registered escalation node with an explicit escalation reason
- LLM-backed nodes may call providers only through `ProviderRouter` with a full `BudgetContext`; direct provider calls bypassing budget checks are invalid
- protected system handlers required by `workflow_profile="ticket_to_pr_v1"` cannot be removed from an activatable config, even if the graph compiles
- the default pipeline template remains available, but the editor is not limited to that single topology
- graph config changes are versioned; the previous version is retained for rollback
- activation requires passing validation + compile; a failed compile cannot be activated

### Graph Config Shadow Mode (dry-run before activation)

Before an admin activates a new graph config, they can run it in **shadow mode** against a replay of recent production webhooks or a curated fixture set. Shadow mode provides empirical evidence of change impact without touching real runs.

- **Shadow runs** — executed on a dedicated worker pool with `shadow=true`. They hit sandboxes normally but use **read-only forks** of repo state; any writes are discarded. PRs are not created. Jira is never notified.
- **Traffic sources** — (a) replay of the last N webhook events for the tenant, (b) hand-picked fixtures from the prompt-regression suite, (c) synthetic tickets for edge cases.
- **Comparison report** — per-ticket diff of outcomes between the active config and the candidate: success/escalation, retry count, budget consumed, agent decisions. Stored under `graph_shadow_runs`.
- **Gate to activation** — an admin cannot activate a candidate that regresses success rate by >5% or increases cost per ticket by >20% vs. the active config, unless they acknowledge with a written justification recorded in audit.
- **Data safety (defense in depth)** — a single `readonly_mode` flag in Python is not sufficient. Shadow runs are isolated at every layer:
  1. **Separate credential set** — every team has a paired read-only `CredentialSet` (`credential_set_shadow_id`) that resolves to a GitHub App installation with `contents:read`, `metadata:read`, `pull_requests:read` only (no write scopes) and a Jira API token with read-only permissions. Shadow workers can only load `credential_set_shadow_id`; regular workers cannot.
  2. **Provider-enforced scopes** — even if application code is bypassed, GitHub/Jira reject write calls at the API boundary because the token has no write scope.
  3. **Separate queue** — `dev-squad:shadow:jobs`; shadow workers cannot subscribe to the primary queue.
  4. **Kubernetes-level isolation** — `worker-shadow` runs under a distinct `ServiceAccount` with no access to the primary credential secrets; NetworkPolicy blocks egress to Jira/GitHub write endpoints and allows only the public repo/issue read surfaces plus the LLM providers.
  5. **Application `readonly_mode=True` flag** — retained as the innermost belt-and-suspenders layer, asserting no write tool is ever invoked.

### Protected Workflow Invariants (v1)

The graph editor is intentionally flexible, but `ticket_to_pr_v1` is not an arbitrary DAG builder. An activatable v1 graph must preserve the business and safety guarantees below:

- there is at least one success terminal and at least one escalation terminal
- every path that reaches a repo-writing node first passes through a planner-owned SDD phase and sets `spec_ready_for_implementation=True`
- every path to `pr_creator` passes through `check_diff_size`, `reviewer`, and `pre_pr_sync`
- every path after a repo-writing node eventually reaches `tester` before `reviewer`
- a human interrupt can be inserted before protected nodes as break-glass control, but a protected guard cannot be removed or bypassed and the success path cannot require manual approval
- if a graph omits a required invariant, validation fails even when `workflow.compile()` succeeds

This keeps the graph editor config-driven without allowing admins to activate flows that violate mandatory v1 controls.

## Default Edge Logic

```python
def should_retry(state: TicketState) -> str:
    # Budget gate: escalate if budget exhausted regardless of retry count
    if state.get("budget_remaining_usd", Decimal("999")) <= 0:
        return "escalate"

    if state.get("tests_passed"):
        return "reviewer"
    if state.get("test_retry_count", 0) < state.get("max_test_retries", 3):
        return "coder"
    return "escalate"

def should_review(state: TicketState) -> str:
    if state.get("budget_remaining_usd", Decimal("999")) <= 0:
        return "escalate"

    if state.get("review_approved"):
        return "pre_pr_sync"   # merge conflict check before PR creation
    if state.get("needs_replan"):
        if state.get("spec_iteration_count", 0) < state.get("max_spec_iterations", 2):
            return "planner"
        return "escalate"
    if state.get("review_retry_count", 0) < state.get("max_review_retries", 2):
        return "coder"
    return "escalate"

def should_create_pr(state: TicketState) -> str:
    """Post-sync merge conflict gate before PR creation."""
    if state.get("merge_conflict_detected"):
        return "escalate"
    return "create_pr"
```

## Diff Size Guard

Before sending code diffs to the reviewer, the system enforces a maximum diff size to prevent context window overflow and ensure meaningful review:

```python
MAX_DIFF_LINES = 2000      # configurable per tenant
MAX_DIFF_FILES = 50         # configurable per tenant

def check_diff_size(state: TicketState) -> str:
    """Route based on diff complexity."""
    if state["diff_line_count"] > MAX_DIFF_LINES:
        return "escalate"    # too large for LLM review
    if len(state["files_changed"]) > MAX_DIFF_FILES:
        return "escalate"
    return "continue"
```

When the diff exceeds limits, the escalation reason includes the sizes so operators can decide to split the ticket.

## Merge Conflict Resolution

Before creating a PR, a dedicated `pre_pr_sync` system node detects and handles base branch drift:

```python
async def pre_pr_sync_node(state: TicketState) -> dict:
    """Rebase work branch on latest base branch before PR creation."""
    current_head = await git_get_head(state["repo_full_name"], state["base_branch"])

    if current_head == state["base_branch_head_at_start"]:
        # No drift, safe to proceed
        return {"merge_conflict_detected": False, "base_branch_head_current": current_head}

    # Attempt automated rebase
    rebase_result = await git_rebase(
        state["work_branch"],
        state["base_branch"],
        repo=state["repo_full_name"],
    )

    if rebase_result.conflicts:
        return {
            "merge_conflict_detected": True,
            "merge_conflict_files": rebase_result.conflicted_files,
            "escalation_reason": f"Merge conflicts in {len(rebase_result.conflicted_files)} files after base branch advanced",
            "escalated": True,
        }

    return {
        "merge_conflict_detected": False,
        "base_branch_head_current": current_head,
    }
```

## Project Structure

```
dev-squad/
├── helm/                              # Helm chart for Kubernetes deployment
│   ├── Chart.yaml
│   ├── values.yaml                    # Base values
│   ├── values-local-minikube.yaml     # Single-cluster local overlay for macOS/Linux dev
│   ├── values-dev.yaml                # Dev overlay
│   ├── values-staging.yaml            # Staging overlay
│   ├── values-prod.yaml               # Production overlay
│   └── templates/
│       ├── api-deployment.yaml
│       ├── api-service.yaml
│       ├── api-hpa.yaml
│       ├── worker-deployment.yaml
│       ├── worker-hpa.yaml
│       ├── worker-shadow-deployment.yaml
│       ├── frontend-deployment.yaml
│       ├── frontend-service.yaml
│       ├── ingress.yaml               # NGINX ingress with TLS
│       ├── postgres-statefulset.yaml   # or external managed DB reference
│       ├── redis-statefulset.yaml      # or external managed Redis reference
│       ├── sandbox-cleanup-cronjob.yaml
│       ├── retention-cleanup-cronjob.yaml
│       ├── sandbox-namespace.yaml      # per-tenant sandbox namespace
│       ├── sandbox-networkpolicy.yaml  # egress whitelist for sandboxes
│       ├── sandbox-resourcequota.yaml  # resource limits per tenant
│       ├── configmap.yaml
│       ├── secrets.yaml               # reference to external secret manager
│       ├── serviceaccount.yaml
│       ├── rbac.yaml
│       ├── prometheus-servicemonitor.yaml
│       ├── prometheus-sloquery.yaml            # SLO recording rules + burn-rate alerts
│       ├── grafana-dashboards-cm.yaml
│       ├── argo-rollout-api.yaml               # Canary definition for API
│       ├── argo-rollout-worker.yaml            # Canary definition for worker
│       ├── poddisruptionbudget.yaml            # PDBs for api + worker
│       ├── topology-spread.yaml                # Multi-AZ spread constraints
│       ├── external-secrets.yaml               # ExternalSecret for Vault/KMS refs
│       ├── kyverno-image-signing.yaml          # Admission policy: signed images only
│       ├── pgbouncer-configmap.yaml            # PgBouncer sidecar config injected into app pods
│       └── status-page-cronjob.yaml            # Periodic health aggregation
├── docker-compose.yml                 # Local development only
├── .env.example
├── Makefile                           # dev shortcuts: make dev, make test, make lint
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini                    # Database migrations
│   ├── alembic/
│   │   └── versions/                  # Migration files
│   ├── docker/
│   │   ├── sandbox.Dockerfile         # Hardened sandbox base image
│   │   └── orchestrator.Dockerfile    # API + worker base image
│   ├── src/
│   │   ├── config.py                  # Settings, env vars, pydantic-settings
│   │   ├── auth/
│   │   │   ├── oidc.py                # OIDC provider integration (Okta/Azure AD/Google)
│   │   │   ├── rbac.py                # Role-based access with granular permissions
│   │   │   ├── middleware.py          # Auth middleware, tenant extraction
│   │   │   └── hmac.py                # HMAC webhook signature verification
│   │   ├── queue/
│   │   │   ├── worker.py              # ARQ worker settings + concurrency config
│   │   │   ├── enqueue.py             # Job enqueue helper with idempotency check
│   │   │   ├── dlq.py                 # Dead letter queue handler
│   │   │   └── graceful.py            # Graceful shutdown signal handler
│   │   ├── graph/
│   │   │   ├── state.py               # TicketState TypedDict
│   │   │   ├── nodes.py               # Node functions (agents created once, reused)
│   │   │   ├── edges.py               # Conditional edge functions (with budget gates)
│   │   │   ├── guards.py              # Diff size guard, merge conflict check, budget check
│   │   │   └── graph.py               # Config-driven StateGraph compiler
│   │   ├── agents/
│   │   │   ├── planner.py             # create_react_agent wrapper
│   │   │   ├── coder.py
│   │   │   ├── tester.py
│   │   │   ├── reviewer.py
│   │   │   └── pr_creator.py
│   │   ├── llm/
│   │   │   ├── router.py              # Provider router with circuit breakers
│   │   │   ├── circuit_breaker.py     # Circuit breaker state machine
│   │   │   ├── metering.py            # Token metering + cost calculation
│   │   │   ├── budget.py              # Budget enforcement + alerts
│   │   │   ├── input_guard.py         # Prompt-injection hardening + delimiter wrapping
│   │   │   └── output_guard.py        # LLM response secret/leak filter
│   │   ├── knowledge/
│   │   │   ├── ingest.py              # Chunking + embedding ingestion into pgvector-backed tables
│   │   │   ├── retrieval.py           # Filtered semantic search and ranking
│   │   │   ├── chunking.py            # Markdown/text splitting policy
│   │   │   └── models.py              # KnowledgeBase + KnowledgeChunk schemas
│   │   ├── billing/
│   │   │   ├── rollup.py              # Hourly → billing_rollup_hourly
│   │   │   ├── rate_card.py           # Price rate card lookup (versioned)
│   │   │   ├── export.py              # CSV/JSONL export for finance/ERP
│   │   │   └── reconcile.py           # Nightly provider invoice reconciliation
│   │   ├── secrets/
│   │   │   ├── vault_client.py        # HashiCorp Vault + KMS client abstraction
│   │   │   ├── envelope.py            # DEK/KEK envelope encryption
│   │   │   ├── rotation.py            # 90-day rotation scheduler + overdue alerts
│   │   │   └── break_glass.py         # Dual-control emergency access
│   │   ├── ratelimit/
│   │   │   ├── limiter.py             # Sliding-window Redis limiter
│   │   │   ├── policies.py            # Per-endpoint-class + per-tenant limits
│   │   │   └── fair_queue.py          # Weighted round-robin dispatcher
│   │   ├── flags/
│   │   │   └── openfeature.py         # OpenFeature provider + kill switches
│   │   ├── safety/
│   │   │   ├── forbidden_paths.py     # Writeset enforcement
│   │   │   ├── pr_sanitizer.py        # Secret redaction in PR body/title
│   │   │   ├── diff_scanner.py        # gitleaks/trufflehog subprocess wrappers
│   │   │   └── branch_protection.py   # Pre-PR branch-protection verification
│   │   ├── tools/
│   │   │   ├── jira_tools.py          # get_ticket, update_status, add_comment
│   │   │   ├── github_tools.py        # create_branch, commit_push, create_pr
│   │   │   ├── sandbox_tools.py       # run_in_sandbox, run_tests, read_file, write_file
│   │   │   ├── git_tools.py           # clone_repo, checkout_branch, diff, rebase
│   │   │   ├── conflict_tools.py      # Merge conflict detection + reporting
│   │   │   └── knowledge_tools.py     # query_knowledge_base, list_knowledge_sources
│   │   ├── services/
│   │   │   ├── sandbox.py             # Kubernetes Job-based sandbox lifecycle
│   │   │   ├── sandbox_security.py    # gVisor config, resource limits, network policies
│   │   │   ├── jira_client.py         # Jira API wrapper (credential-isolated)
│   │   │   ├── github_client.py       # GitHub API wrapper (credential-isolated)
│   │   │   ├── credential_vault.py    # Credential decryption + injection (never to LLM)
│   │   │   └── knowledge_service.py   # pgvector-backed retrieval service wrapper
│   │   ├── tenancy/
│   │   │   ├── models.py              # Tenant, Team, CredentialSet models
│   │   │   ├── resolver.py            # Webhook → tenant/team resolution
│   │   │   └── isolation.py           # Row-level security + namespace enforcement
│   │   ├── observability/
│   │   │   ├── metrics.py             # Prometheus metrics registry
│   │   │   ├── logging.py             # Structured JSON logging (structlog) + PII scrub
│   │   │   ├── tracing.py             # OpenTelemetry setup + span processor (PII scrub)
│   │   │   ├── slo.py                 # SLO/burn-rate recording rules
│   │   │   ├── status_page.py         # Status page component state aggregation
│   │   │   └── health.py              # Health + readiness probes
│   │   ├── retention/
│   │   │   ├── policy.py              # Data retention policy definitions
│   │   │   └── cleanup.py             # Scheduled cleanup jobs (CronJob)
│   │   ├── storage/
│   │   │   ├── config_repo.py         # Config CRUD backed by PostgreSQL (versioned)
│   │   │   ├── audit_log.py           # Immutable audit trail for all config changes
│   │   │   └── migrations.py          # Alembic migration helpers
│   │   └── api/
│   │       ├── main.py                # FastAPI app with middleware stack (auth, rate, otel)
│   │       ├── versioning.py          # /api/v1 router, OpenAPI diff harness
│   │       └── routes/
│   │           ├── webhooks.py        # Jira webhook endpoint (idempotent, replay-safe)
│   │           ├── status.py          # Execution status API (tenant-scoped)
│   │           ├── stream.py          # SSE endpoint (tenant-scoped, Redis pub/sub)
│   │           ├── admin.py           # Agent config + dry-run API (admin role)
│   │           ├── graph.py           # Graph config, compile, validation, shadow, rollback
│   │           ├── assets.py          # Sprite upload/manifest API
│   │           ├── auth.py            # OIDC callback + session endpoints
│   │           ├── tenants.py         # Tenant/team CRUD (super-admin)
│   │           ├── metering.py        # Cost/usage reporting endpoints
│   │           ├── billing.py         # Billing export endpoints (super_admin)
│   │           ├── status_page.py     # Public component health (unauthenticated)
│   │           └── health.py          # /healthz, /readyz endpoints
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_graph.py
│   │   │   ├── test_nodes.py
│   │   │   ├── test_tools.py
│   │   │   ├── test_services.py
│   │   │   ├── test_circuit_breaker.py
│   │   │   ├── test_metering.py
│   │   │   ├── test_budget.py
│   │   │   ├── test_merge_conflict.py
│   │   │   ├── test_diff_guard.py
│   │   │   ├── test_idempotency.py
│   │   │   ├── test_tenant_isolation.py
│   │   │   ├── test_prompt_injection.py
│   │   │   ├── test_forbidden_paths.py
│   │   │   ├── test_pr_sanitizer.py
│   │   │   ├── test_rate_limiter.py
│   │   │   ├── test_fair_queue.py
│   │   │   └── test_envelope_encryption.py
│   │   ├── integration/
│   │   │   ├── test_webhook_to_queue.py        # Webhook → ARQ enqueue
│   │   │   ├── test_graph_execution.py         # Full graph run against test repo
│   │   │   ├── test_sandbox_lifecycle.py       # Sandbox creation → execution → cleanup
│   │   │   ├── test_checkpoint_resume.py       # Failure → checkpoint → resume
│   │   │   ├── test_oidc_flow.py               # Auth end-to-end
│   │   │   ├── test_multi_tenant.py            # Cross-tenant isolation validation
│   │   │   ├── test_migrations_reversible.py   # Every Alembic migration round-trips
│   │   │   ├── test_pitr_restore.py            # Postgres PITR to scratch env
│   │   │   ├── test_kek_rotation.py            # KEK rotation + re-wrap under load
│   │   │   └── test_graph_shadow_mode.py       # Shadow run comparison harness
│   │   ├── e2e/
│   │   │   ├── test_ticket_to_pr.py            # Simulated Jira webhook → PR creation
│   │   │   ├── test_escalation_flow.py         # Max retries → human escalation
│   │   │   ├── test_budget_exhaustion.py       # Budget cap → graceful stop
│   │   │   └── test_provider_failover.py       # Primary down → fallback model
│   │   ├── chaos/
│   │   │   ├── test_llm_garbage_response.py    # LLM returns invalid output
│   │   │   ├── test_all_providers_unavailable.py # Primary + fallback both hard-down
│   │   │   ├── test_sandbox_crash.py           # Docker/K8s sandbox dies mid-execution
│   │   │   ├── test_sandbox_timeout.py         # Job hits activeDeadlineSeconds
│   │   │   ├── test_db_connection_loss.py       # PostgreSQL goes down
│   │   │   ├── test_redis_partition.py          # Redis cluster partition
│   │   │   ├── test_worker_kill.py             # Worker pod killed during job
│   │   │   ├── test_az_failure.py              # Simulated AZ loss, failover within RTO
│   │   │   ├── test_vault_unavailable.py       # Secrets store outage
│   │   │   ├── test_budget_race.py             # Concurrent nodes cannot exceed cap
│   │   │   └── test_noisy_neighbor.py          # Weighted fair queue under pressure
│   │   ├── prompt_regression/
│   │   │   ├── fixtures/                        # Known-good input/output pairs
│   │   │   ├── test_planner_regression.py       # Planner prompt stability
│   │   │   ├── test_reviewer_regression.py      # Reviewer structured output stability
│   │   │   └── conftest.py                      # LangSmith evaluation fixtures
│   │   ├── fuzz/
│   │   │   ├── test_webhook_fuzz.py             # schemathesis against /api/v1/webhooks
│   │   │   ├── test_admin_api_fuzz.py           # OpenAPI-driven admin API fuzz
│   │   │   └── test_graph_config_fuzz.py        # Hypothesis strategies for GraphConfig
│   │   └── conftest.py
│   └── scripts/
│       ├── seed_test_repo.sh                    # Create test repo for E2E
│       ├── run_chaos.sh                         # Chaos test runner
│       ├── dr_restore_drill.sh                  # Quarterly DR restore drill
│       └── rotate_kek.sh                        # Staged KEK rotation + DEK re-wrap
├── docs/
│   ├── runbooks/
│   │   ├── dr.md                                # Disaster recovery procedure
│   │   ├── postmortem-template.md
│   │   ├── slo-error-budget-policy.md
│   │   ├── incident-severity.md
│   │   ├── break-glass-credentials.md
│   │   ├── all-providers-down.md                # Simultaneous LLM provider outage
│   │   ├── air-gapped-deployment.md             # Offline install, catalogue validation
│   │   └── alerts/                              # One runbook per alert rule
│   ├── adr/                                     # Architecture decision records
│   ├── compliance/
│   │   ├── dpa-template.md
│   │   ├── soc2-control-matrix.md
│   │   └── gdpr-erasure-procedure.md
│   └── api/
│       └── openapi-v1.yaml                      # Published API contract
├── frontend/                                    # Vite + React + TypeScript (single app)
│   ├── package.json
│   ├── Dockerfile
│   ├── nginx.conf                               # Production NGINX config
│   ├── vite.config.ts
│   ├── public/
│   │   └── pixel-art/                           # Pixel art assets reused/adapted from the-dev-squad
│   └── src/
│       ├── App.tsx
│       ├── router.tsx                           # Shared routes + role guards
│       ├── lib/
│       │   ├── api-client.ts
│       │   ├── auth-store.ts                    # Session + role state (OIDC)
│       │   ├── use-pipeline.ts                  # SSE consumer hook (tenant-scoped)
│       │   └── use-metering.ts                  # Cost/usage display hook
│       ├── pages/
│       │   ├── login.tsx                        # OIDC redirect login
│       │   ├── dashboard.tsx                    # Visible to authenticated users
│       │   ├── admin.tsx                        # Visible only to admin users
│       │   ├── graph-editor.tsx                 # Visual graph editor
│       │   └── cost-dashboard.tsx               # LLM cost/usage reporting
│       └── components/                          # Shared UI components (details at implementation time)
```

## Infrastructure (Kubernetes)

### Production Workload Topology

Production uses four workload zones: `dev-squad-app`, `dev-squad-data`, `dev-squad-observability`, and per-tenant `sandbox-<tenant>` namespaces. The edge ingress controller may be a shared cluster/platform component, but the workloads below are the production baseline the system itself depends on.

#### Application & Data Workloads

| Resource | Kind | Replicas | Namespace | Purpose |
|---|---|---|---|---|
| frontend | Deployment | 2 | `dev-squad-app` | Vite React app served via NGINX |
| api | Deployment + HPA | 2-6 | `dev-squad-app` | FastAPI app (webhook receiver, admin, status, SSE) |
| worker | Deployment + HPA | 2-10 | `dev-squad-app` | Primary ARQ/LangGraph execution pool |
| worker-shadow | Deployment | 1-2 | `dev-squad-app` | Dedicated read-only shadow-mode pool for config replay and dry-run evaluation |
| external-secrets-operator | Deployment | 2 | `dev-squad-app` | Sync runtime secrets from Vault into Kubernetes Secrets |
| postgres | StatefulSet or managed HA service | 1 primary + 1 sync replica + 1 async replica | `dev-squad-data` | Checkpoints, memory, config, metering, audit, optional pgvector knowledge index |
| redis | StatefulSet or managed HA service | 3 primaries + 3 replicas | `dev-squad-data` | ARQ queue, SSE pub/sub, idempotency, rate limiting |
| sandbox | Job (ephemeral) | `0..N` per tenant | `sandbox-<tenant>` | Hardened isolated execution for code/test steps |

#### Observability Workloads

| Resource | Kind | Replicas | Namespace | Purpose |
|---|---|---|---|---|
| prometheus | StatefulSet or HA pair | 2 | `dev-squad-observability` | Metrics scrape, recording rules, alert evaluation |
| alertmanager | StatefulSet | 3 | `dev-squad-observability` | Deduplicated alert fan-out and silences |
| grafana | Deployment | 2 | `dev-squad-observability` | Dashboards, drill-down, on-call visibility |
| loki | StatefulSet (simple scalable) | 3 | `dev-squad-observability` | Structured log storage/query |
| tempo | StatefulSet | 3 | `dev-squad-observability` | Distributed trace storage/query |

Cluster-level collectors such as `promtail`, `kube-state-metrics`, and `node-exporter` are expected in production but are treated as platform add-ons rather than app-owned workloads.

#### Maintenance Jobs

| Resource | Kind | Schedule | Namespace | Purpose |
|---|---|---|---|---|
| sandbox-cleanup | CronJob | every 15 minutes | `dev-squad-app` | Delete orphaned sandbox Jobs/pods/volumes |
| retention-cleanup | CronJob | every 6 hours | `dev-squad-app` | Enforce retention windows for checkpoints, memory, DLQ, and metering partitions |
| status-page-sync | CronJob | every 1-5 minutes | `dev-squad-app` | Publish summarized component health to the public status page/provider |

`PgBouncer` is injected as a sidecar into `api`, `worker`, and `worker-shadow` pods, so it does not appear as a standalone row in the workload inventory.

### Environment Profile: `local-minikube`

`local-minikube` is the explicit workstation profile for macOS/Linux development. It validates manifests, namespaces, ESO/Vault wiring, ingress, queueing, sandbox Jobs, and the core agent loop, but it does **not** attempt to emulate production HA, multi-AZ, or full observability retention.

#### Minikube prerequisites

- **Driver** — `vfkit` on modern macOS (`docker` is acceptable if already standardized locally).
- **Addons enabled** — `ingress`, `metrics-server`.
- **Optional addons** — `gvisor` for sandbox runtime approximation; `csi-hostpath-driver` if you run a multi-node local cluster and need PVCs.
- **Node count** — `1` by default; `2` only when validating anti-affinity, scheduling, or multi-node behavior.

#### Workload overrides

| Resource | Production | `local-minikube` | Notes |
|---|---|---|---|
| frontend | `2` replicas | `1` replica | No HA locally |
| api | `2-6` + HPA | `1` replica, HPA disabled | Use fixed replica for predictable debugging |
| worker | `2-10` + HPA | `1` replica, HPA disabled | Single execution lane by default |
| worker-shadow | `1-2` replicas | `0` replicas by default | Enable manually only when testing shadow mode |
| external-secrets-operator | `2` replicas | `1` replica | Single operator is enough locally |
| Vault | external HA control plane | `1` in-cluster dev-mode pod | Official Vault Helm chart with `server.dev.enabled=true`; non-persistent |
| postgres | `1 primary + 1 sync + 1 async` | `1` standalone pod | No HA, no replica routing; `pgvector` extension remains enabled for local RAG testing |
| redis | `3 primaries + 3 replicas` cluster | `1` standalone pod | No Redis Cluster in local profile |
| sandbox jobs | `0..N` per tenant | max `1` concurrent sandbox per tenant | Concurrency cap keeps laptop stable |
| prometheus | `2` replicas | `0` by default | Enable only if debugging metrics export |
| alertmanager | `3` replicas | disabled | Local alerts are noise |
| grafana | `2` replicas | disabled by default | Optional when validating dashboards |
| loki | `3` replicas | disabled | Use `kubectl logs` locally |
| tempo | `3` replicas | disabled | Keep tracing lightweight locally |
| sandbox-cleanup | enabled | enabled | Keep ephemeral jobs tidy |
| retention-cleanup | enabled | disabled by default | Run manually when needed |
| status-page-sync | enabled | disabled | No public status page in local profile |

#### Secrets profile

| Concern | Production | `local-minikube` |
|---|---|---|
| Secret authority | External Vault HA | In-cluster Vault dev mode |
| Vault auth path | Kubernetes auth via ESO `ClusterSecretStore` | Token-based `SecretStore` bootstrap is allowed |
| Persistence | Durable HA storage + audit log | Ephemeral; reset on cluster rebuild |
| Auto-unseal | Required | Not required |
| Root token handling | Never used by app workloads | Allowed for local bootstrap only |

#### Exact differences vs `prod`

- `local-minikube` disables all HA assumptions: no multi-AZ, no replica failover, no Redis Cluster, no Postgres replicas.
- `local-minikube` disables cost-heavy observability components by default: `alertmanager`, `loki`, `tempo`, and usually `grafana`/`prometheus`.
- `local-minikube` disables `worker-shadow` unless the developer is explicitly validating graph shadow mode.
- `local-minikube` keeps `ingress` and `metrics-server` enabled because they are necessary to validate routing and any HPA-related manifests, even if HPAs themselves are disabled by default.
- `local-minikube` relaxes the secret bootstrap path to Vault dev mode with a local token, but this exception is forbidden in `dev`, `staging`, and `prod`.
- `local-minikube` keeps `sandbox-cleanup` but disables `status-page-sync` and usually `retention-cleanup` because those jobs add noise without improving local feedback loops.
- `local-minikube` should be treated as a functional integration environment, not as evidence for HA, SLO, DR, or security-hardening acceptance.

### Worker Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Pods
      pods:
        metric:
          name: arq_active_jobs
        target:
          type: AverageValue
          averageValue: "2"            # scale when avg > 2 active jobs/pod
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 120
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 300
```

### Worker Configuration

```python
class WorkerSettings:
    """ARQ worker settings with production-grade queue management."""

    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
    )

    max_jobs: int = 3                     # concurrent jobs per worker pod
    job_timeout: timedelta = timedelta(minutes=90)    # hard timeout per ticket (whole run)
    max_tries: int = 1                    # retries handled by LangGraph, not ARQ

    # Timeout hierarchy (all configurable per tenant):
    # - job_timeout (90 min)          — whole ticket, enforced by ARQ
    # - node_timeout (15 min)         — one LangGraph node, enforced by tenacity wrapper
    # - sandbox activeDeadlineSeconds — one K8s Job invocation (30 min), enforced by K8s
    # - llm_timeout (120s)            — single LLM call, enforced by httpx client
    # sandbox timeout MUST be >= the longest expected single step (typically
    # coder + install + full test suite for a medium repo). A hit on
    # activeDeadlineSeconds escalates with reason="sandbox_timeout" and does
    # not count against test_retry_count.
    health_check_interval: int = 30       # seconds
    queue_name: str = "dev-squad:jobs"
    retry_jobs: bool = False              # LangGraph checkpointing handles retries

    # Dead letter queue
    dlq_queue_name: str = "dev-squad:dlq"
    on_job_failure = handle_dead_letter    # move to DLQ + alert

    # Graceful shutdown
    on_shutdown = graceful_shutdown_handler
```

### Shadow Worker Pool

Shadow-mode runs must not contend with the primary execution queue or accidentally gain write privileges. They use the same container image as `worker`, but a separate deployment and queue:

```python
class ShadowWorkerSettings(WorkerSettings):
    queue_name: str = "dev-squad:shadow:jobs"
    max_jobs: int = 1                      # predictable replay load, avoid starving prod
    retry_jobs: bool = False
    shadow_mode: bool = True
    readonly_mode: bool = True             # innermost guard — service layer blocks writes
    credential_field: str = "credential_set_shadow_id"  # read-only cred set only
    service_account: str = "dev-squad-worker-shadow"    # K8s SA with no write-secret access
```

Extend `CredentialSet` with a shadow counterpart:

```python
class Team(BaseModel):
    ...
    credential_set_id: str                      # production credentials (read-write)
    credential_set_shadow_id: str               # read-only credentials for shadow runs

# The GitHub App installation backing credential_set_shadow_id is configured
# with the minimal permission set: {contents:read, metadata:read,
# pull_requests:read}. No issues:write, no workflows. Jira tokens for shadow
# are created from a dedicated read-only service account in Jira.
```

### Graceful Shutdown

Workers must drain in-flight jobs before terminating. This prevents checkpoint corruption and lost work:

```python
async def graceful_shutdown_handler(ctx: dict) -> None:
    """Handle SIGTERM gracefully during Kubernetes rolling updates."""
    logger.info("Graceful shutdown initiated, draining active jobs...")

    # ARQ stops accepting new jobs automatically on SIGTERM
    # Wait for in-flight jobs to reach a checkpoint boundary
    active_jobs = ctx.get("active_jobs", [])
    for job in active_jobs:
        # Each LangGraph node checkpoints on completion
        # Wait up to termination_grace_period for current node to finish
        await job.wait_for_checkpoint(timeout=settings.TERMINATION_GRACE_PERIOD)

    logger.info("All active jobs checkpointed, shutting down cleanly")
```

Kubernetes pod spec uses `terminationGracePeriodSeconds: 120` to allow workers time to checkpoint.

### Dead Letter Queue

Jobs that exhaust their timeout or fail with unrecoverable errors are moved to a DLQ:

```python
async def handle_dead_letter(ctx: dict, job: Job, exc: Exception) -> None:
    """Move failed jobs to DLQ with full context for debugging."""
    dlq_entry = {
        "job_id": job.job_id,
        "ticket_key": job.kwargs.get("ticket_key"),
        "tenant_id": job.kwargs.get("tenant_id"),
        "error": str(exc),
        "traceback": traceback.format_exc(),
        "enqueued_at": job.enqueue_time.isoformat(),
        "failed_at": datetime.utcnow().isoformat(),
        "retry_eligible": not isinstance(exc, (BudgetExhaustedError, SecurityViolationError)),
    }

    await ctx["redis"].lpush(WorkerSettings.dlq_queue_name, json.dumps(dlq_entry))

    # Alert via Prometheus metric + optional PagerDuty/Slack webhook
    dlq_counter.labels(tenant_id=dlq_entry["tenant_id"]).inc()
    logger.error("Job moved to DLQ", extra={"dlq_entry": dlq_entry})
```

DLQ entries are visible in the admin UI. Admins can inspect, retry, or dismiss DLQ items.

### Sandbox Hardening (Kubernetes + gVisor)

Sandboxes run as Kubernetes Jobs with gVisor (runsc) runtime class for kernel-level isolation:

```yaml
# sandbox-job-template.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: sandbox-${TICKET_KEY}-${HASH}
  namespace: sandbox-${TENANT_ID}
  labels:
    app: dev-squad-sandbox
    tenant: ${TENANT_ID}
    ticket: ${TICKET_KEY}
spec:
  activeDeadlineSeconds: 1800        # 30 min hard timeout per sandbox invocation
  backoffLimit: 0                    # no K8s-level retry
  template:
    spec:
      runtimeClassName: gvisor       # kernel isolation via runsc
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 65534             # nobody
        runAsGroup: 65534
        fsGroup: 65534
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: sandbox
          image: ${SANDBOX_IMAGE}    # pre-scanned, pinned digest
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2"
              ephemeral-storage: "5Gi"
          env:
            - name: TICKET_KEY
              value: ${TICKET_KEY}
            # NO credentials in env — mounted read-only from sealed secret
          volumeMounts:
            - name: workspace
              mountPath: /workspace
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: workspace
          emptyDir:
            sizeLimit: 5Gi
        - name: tmp
          emptyDir:
            sizeLimit: 1Gi
      restartPolicy: Never
      terminationGracePeriodSeconds: 30
```

### Sandbox Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sandbox-egress-whitelist
  namespace: sandbox-${TENANT_ID}
spec:
  podSelector:
    matchLabels:
      app: dev-squad-sandbox
  policyTypes:
    - Egress
    - Ingress
  ingress: []                        # no inbound traffic allowed
  egress:
    # DNS resolution
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
        - podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
    # Package registries only (via corporate proxy when available)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - protocol: TCP
          port: 443
        - protocol: TCP
          port: 80
      # Further restricted by proxy or firewall rules to:
      # - pypi.org, files.pythonhosted.org
      # - registry.npmjs.org
      # - rubygems.org
      # - proxy.golang.org
      # All other egress is blocked
```

### Sandbox Image Security

```dockerfile
# sandbox.Dockerfile — hardened base
FROM python:3.12-slim-bookworm AS base

# Security: no root, no setuid, minimal packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    find / -perm /6000 -type f -exec chmod a-s {} \;

# Non-root user
RUN groupadd -r sandbox && useradd -r -g sandbox -d /workspace sandbox
USER sandbox
WORKDIR /workspace

# Healthcheck for readiness
HEALTHCHECK --interval=10s --timeout=3s CMD ["true"]
```

Sandbox images are:
- Built from a pinned base image with hash digest (not `:latest`)
- Scanned by Trivy/Grype in CI before promotion
- Stored in a private registry with image signing (cosign)
- Rotated on a scheduled cadence (weekly rebuild + scan)

### Sandbox Cleanup

A dedicated Kubernetes CronJob named `sandbox-cleanup` runs every 15 minutes to clean up orphaned sandbox resources:

```python
async def cleanup_orphaned_sandboxes() -> None:
    """Remove sandbox pods/jobs/volumes that exceed their TTL."""
    # Find completed/failed sandbox jobs older than 30 minutes
    # Find running sandbox jobs older than activeDeadlineSeconds + buffer
    # Delete the jobs and their associated emptyDir volumes
    # Log all cleanup actions with tenant_id and ticket_key
```

### Resource Quotas per Tenant

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: sandbox-quota
  namespace: sandbox-${TENANT_ID}
spec:
  hard:
    pods: "10"                       # max concurrent sandboxes per tenant
    requests.cpu: "10"
    requests.memory: "10Gi"
    limits.cpu: "20"
    limits.memory: "20Gi"
    requests.ephemeral-storage: "50Gi"
```

## Authentication & Authorization (OIDC + RBAC)

### OIDC Integration

```python
class AuthSettings(BaseSettings):
    """OIDC provider configuration. Supports Okta, Azure AD, Google Workspace."""
    oidc_issuer: str                       # "https://login.microsoftonline.com/{tenant}/v2.0"
    oidc_client_id: str
    oidc_client_secret: str                # stored in K8s secret
    oidc_audience: str
    oidc_scopes: list[str] = ["openid", "profile", "email", "groups"]
    oidc_redirect_uri: str                 # "https://devsquad.company.com/api/auth/callback"

    # Group-to-role mapping (configured by super-admin)
    role_mapping: dict[str, str] = {
        "devsquad-viewers": "viewer",
        "devsquad-operators": "operator",
        "devsquad-admins": "admin",
        "devsquad-platform": "super_admin",
    }
```

### Role Hierarchy

| Role | Permissions | Scope |
|---|---|---|
| `viewer` | View dashboard, job status, SSE streams | Own tenant + team(s) |
| `operator` | Viewer + approve/deny interrupts, retry failed jobs, inspect DLQ | Own tenant + team(s) |
| `admin` | Operator + agent config CRUD, graph editing, sprite upload, dry-run testing, cost reports | Own tenant (all teams) |
| `super_admin` | Admin + tenant/team CRUD, credential management, cross-tenant visibility, system config | All tenants |

### Session Management

- Sessions are stateless JWTs with short TTL (15 minutes) + refresh tokens stored in HttpOnly cookies
- Refresh tokens are tracked in PostgreSQL for revocation capability
- Token revocation endpoint invalidates all sessions for a user (used on credential rotation or security incident)
- MFA enforcement is delegated to the OIDC provider (Okta/Azure AD policy)
- Frontend uses PKCE flow for OIDC code exchange

```python
class SessionToken(BaseModel):
    sub: str                   # OIDC subject ID
    tenant_id: str
    team_ids: list[str]
    role: str                  # highest role from group mapping
    exp: int                   # 15 min from issue
    jti: str                   # unique token ID for revocation tracking
```

## Rate Limiting & Abuse Prevention

Layered rate limits protect the system from runaway tenants, credential abuse, and cost spikes. Limits are enforced at three layers:

| Layer | Where | Keyed by | Default Limit | Purpose |
|---|---|---|---|---|
| Edge | NGINX ingress | source IP | 100 req/min | Absorb DoS/burst traffic |
| Application | FastAPI middleware (slowapi + Redis) | `tenant_id + endpoint_class` | see table below | Fair allocation across tenants |
| Webhook | `/webhooks/jira` | `tenant_id + ticket_key` | 20 events/min/ticket | Stop webhook flood loops |
| LLM outbound | ProviderRouter | `tenant_id + provider` | provider account quota | Honor provider TPM/RPM |
| Queue | ARQ dispatcher | `tenant_id` | `max_concurrent_jobs_per_tenant` | Noisy-neighbor protection |

### Per-endpoint class limits

| Endpoint class | Limit (per tenant) | Burst |
|---|---|---|
| `webhook` | 600/min | 100 |
| `status_read` | 300/min | 60 |
| `sse_stream` | 50 concurrent | — |
| `admin_write` | 60/min | 20 |
| `admin_test` (dry-run) | 10/min | 5 |
| `superadmin` | 30/min | 10 |

```python
class RateLimitConfig(BaseModel):
    tenant_id: str
    endpoint_class: str
    limit_per_minute: int
    burst: int
    window: Literal["sliding", "fixed"] = "sliding"

class RateLimiter:
    """Redis-backed sliding window rate limiter with per-tenant overrides."""

    async def check(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        ...  # returns (allowed, retry_after_seconds, remaining)
```

429 responses include `Retry-After` and `X-RateLimit-{Limit,Remaining,Reset}` headers. Rate-limit events are emitted as Prometheus metrics (`devsquad_rate_limited_total`) and logged with `tenant_id`, `endpoint_class`, `ip_hash` for abuse analysis.

### Queue Fairness (Weighted Round-Robin)

ARQ's native FIFO would let one heavy tenant starve others. The worker dispatcher wraps ARQ with a weighted fair queue:

- Each tenant is assigned a `queue_weight` (default 1; super_admin can raise priority for paid tiers).
- Each worker pulls the next job using **deficit round-robin** across a per-tenant queue set (`dev-squad:jobs:{tenant_id}`).
- A tenant may not occupy more than `max_concurrent_jobs_per_tenant` (default 3) of the worker pool at once; additional jobs stay queued.
- Starvation protection: any queued job waiting > 5 minutes is promoted to the next dispatch regardless of weight.
- Metrics: `devsquad_queue_depth{tenant_id}`, `devsquad_queue_wait_seconds{tenant_id}`, `devsquad_tenant_concurrency{tenant_id}`.

```python
class FairDispatcher:
    """Weighted-fair job dispatcher on top of ARQ."""

    async def next_job(self, worker_pod: str) -> Job | None:
        # 1. enumerate non-empty tenant queues
        # 2. filter out tenants at max concurrency
        # 3. select by deficit round-robin + weight
        # 4. promote any job waiting > starvation_threshold
        ...
```

## Security & Compliance Baseline

A single document-level contract for security. Everything below is mandatory for v1 and is enforced in CI, runtime, or both.

### Prompt Injection & LLM Input Hardening

External content (Jira ticket bodies, repo READMEs, diffs of modified files) is treated as **untrusted input** that could contain prompt-injection payloads targeting the agents.

- **Input framing** — Every untrusted blob is wrapped in delimited XML tags (`<jira_ticket>...</jira_ticket>`) with the system prompt explicitly instructing the agent to treat the contents as data, never as instructions.
- **Instruction allowlist** — Agents check tool-call chains against an allowlist. A planner that tries to invoke PR creation, or a reviewer that tries to execute in the sandbox, is blocked and the run escalates with `escalation_reason = "tool_policy_violation"`.
- **Response filter** — Every LLM response is run through a lightweight output classifier that flags attempts to exfiltrate environment variables, credentials patterns, known prompt-leak phrases (e.g., "ignore previous instructions"), or base64 blobs above a threshold length.
- **Secondary-confirm on sensitive actions** — Any PR that touches security-sensitive paths (`.github/workflows/**`, `**/Dockerfile`, `**/*.env*`, `infra/**`, `helm/**`, dependency lockfiles) is auto-routed through a `security_review` interrupt regardless of size.
- **No tool discovery from ticket text** — Agents cannot be granted new tools through content in the ticket; tool grants come only from the activated agent config.

### Repository & PR Safety Rails

- **Forbidden-path writeset** — A backend-enforced list of paths the Coder/PR Creator agents cannot modify: `main` branch, `release/*`, `.github/workflows/**`, `.circleci/**`, `infra/**`, `helm/**`, root `Dockerfile`, secret files (`**/*.pem`, `**/.env*`, `**/*.key`), `CODEOWNERS`, `SECURITY.md`. Writes to these paths hit the `security_review` interrupt.
- **Branch protection contract** — The target base branch must have server-side branch protection (required reviews, required status checks, no force-push). If protection is missing, PR creation is blocked with `escalation_reason = "branch_protection_missing"`.
- **Force-push prohibited** — Git wrapper refuses `--force` / `--force-with-lease` for all agents; only human operators can force-push via explicit break-glass flow.
- **PR body sanitization** — Before posting, PR title/body are run through gitleaks + a regex suite for API keys, JWTs, AWS secrets, private keys, and PII patterns. Matches are redacted and the run logs `pr_secret_redaction` with span of original content hash.
- **Diff secret scanning** — gitleaks runs against the working tree after every Coder node. Any finding halts the run and escalates with `escalation_reason = "secret_detected_in_diff"`.
- **Signed commits** — All agent-authored commits are signed with a per-tenant Sigstore (cosign keyless) identity for downstream provenance. Unsigned commits are rejected by branch protection.
- **PR authorship transparency** — Every PR body ends with a standardized `Generated-By: dev-squad/<version> run_id=<uuid>` trailer and links to the audit log entry.

### Supply Chain Security

- **SBOM on every image** — `syft` produces CycloneDX SBOMs for `orchestrator` and `sandbox` images; SBOMs are uploaded to the artifact registry alongside the image.
- **Image signing (cosign keyless)** — All images are signed against a GitHub/GitLab OIDC identity. Kubernetes admission (Kyverno or Sigstore policy-controller) rejects unsigned images at deploy time.
- **SLSA Level 3 provenance** — CI emits SLSA provenance attestations; attestations are verified before promotion to staging/prod.
- **Dependency scanning** — Trivy + Grype + OSV-Scanner in CI on every PR, blocking on critical/high vulnerabilities with no accepted exception. Exceptions require a dated expiry and a ticket reference.
- **License compliance** — FOSSA or ScanCode enforces a license allowlist (MIT, Apache-2.0, BSD-3, ISC, MPL-2.0). Copyleft licenses (GPL/AGPL) are blocked by default and require super_admin exception.
- **Automated dependency updates** — Renovate with grouped PRs, auto-merge for patch-level security updates that pass CI, weekly digest for minor/major.
- **Pinned base images** — All Dockerfiles reference digests, not tags. Renovate keeps digests fresh; `:latest` is banned by CI linting.
- **Reproducible builds** — Container builds are performed with fixed timestamps and sorted manifests so identical inputs produce byte-identical images.

### Secret & Credential Hygiene

- **Zero secrets in LLM context** — Enforced by credential vault layer; every outbound LLM prompt is scrubbed for secret-pattern matches (last-chance belt-and-suspenders).
- **Zero secrets in structured logs** — structlog processor redacts any field matching secret patterns; a unit test suite asserts redaction on known inputs.
- **Pre-commit + CI secret scanning** — gitleaks + trufflehog run on developer workstations (pre-commit) and in CI. Any detection blocks the commit/PR.
- **Secrets rotation SLA** — LLM provider keys rotated every 90 days; GitHub App signing keys every 180 days; Vault/KMS KEKs every 12 months with staged re-wrap.
- **Secret access auditing** — Every secret read from Vault emits an audit event with actor, tenant, and purpose; anomalous read patterns trigger an alert.

### Data Classification & Handling

| Class | Examples | Rules |
|---|---|---|
| Public | Open-source docs, public SBOMs | No restrictions |
| Internal | PR metadata, commit SHAs | Tenant-scoped access, logged reads |
| Confidential | Source code in LLM context, ticket bodies | DPA required; encrypted in transit + at rest; short retention |
| Restricted | Credentials, KEKs, DEKs | HSM-bound; never leaves KMS boundary; break-glass access |

### Compliance Mapping

| Control | Implementation | Evidence |
|---|---|---|
| SOC 2 CC6 (access) | OIDC + RBAC + per-tenant isolation + audit log | `audit_log` table, SSO logs, role mapping config |
| SOC 2 CC7 (monitoring) | Prometheus + alerts + DLQ + anomaly detection | Grafana dashboards, alert history |
| SOC 2 CC8 (change mgmt) | Config versioning + approvals + CI gates | `config_entries` versions, PR history |
| ISO 27001 A.12.6 (vuln mgmt) | Trivy/Grype + Renovate + patch SLA | CI scan reports, Renovate PR history |
| GDPR Art. 32 (security) | Envelope encryption, pseudonymization, DPA | Crypto inventory, DPA acknowledgments |
| GDPR Art. 17 (erasure) | Tenant-delete cascade + audit pseudonymization | Runbook + deletion audit events |

## Disaster Recovery & High Availability

### Availability Targets

| Component | SLO | Multi-AZ | Failover |
|---|---|---|---|
| API (FastAPI) | 99.9% | Yes — 3 AZ | Automatic (K8s scheduler + HPA) |
| Worker pool | 99.5% | Yes — 3 AZ | Automatic; in-flight jobs resume from checkpoint |
| Shadow worker pool | 99.5% | Yes — 3 AZ | Automatic; replay jobs can be requeued without affecting live traffic |
| PostgreSQL primary | 99.95% | Yes — 1 primary + 1 sync replica + 1 async replica across 3 AZ | Automatic via Patroni or cloud-managed HA |
| Redis | 99.9% | Yes — 3 primaries + 3 replicas across 3 AZ | Automatic via Redis Cluster gossip |
| Object storage (sprites) | 99.99% | Provider-managed (S3/GCS) | Provider-managed |
| LLM providers | 99% (per provider) | N/A | Automatic circuit breaker failover |

### RPO / RTO

| Scenario | RPO | RTO | Strategy |
|---|---|---|---|
| Pod loss (API/worker) | 0 | < 60s | K8s reschedule; checkpoint resume |
| AZ loss | 0 | < 5 min | Multi-AZ scheduling + DB sync replica promotion |
| DB primary loss | ≤ 30s | ≤ 5 min | Sync streaming replica + automatic failover |
| Region loss | ≤ 15 min | ≤ 2 hours | Cross-region PITR restore from pgBackRest + Velero |
| Accidental delete / corruption | 0 (PITR to second granularity) | ≤ 30 min | PITR restore to separate cluster, validate, cutover |
| Ransomware / malicious delete | ≤ 1 hour | ≤ 4 hours | Immutable offsite backups + break-glass restore |

### Backup Strategy

- **PostgreSQL** — pgBackRest with WAL archiving to S3/GCS. Full daily backup, incremental every 4 hours. Retention: 30 days hot + 180 days cold (Glacier/Coldline). Encryption: SSE-KMS per backup, keys in a separate account/project.
- **Config & audit data** — Covered by PG backups; additionally, the `audit_log` table is streamed via logical replication to a write-once S3 bucket (Object Lock, Governance mode) for tamper evidence.
- **Kubernetes state** — Velero snapshots cluster resources (minus Secrets/Credentials, which are Vault-native) daily.
- **Object storage (sprites)** — Versioning + cross-region replication + lifecycle rules (retain 90 days after deletion).
- **Redis** — Redis is treated as cache/ephemeral; RDB snapshots every 15 minutes for forensic-only purposes. No restore SLA.

### Restore Testing

- **Quarterly game day** — A full PITR restore is executed to a scratch environment every quarter. The drill includes validating schema, row counts, a synthetic webhook-to-PR flow, and cutover rehearsal. A failed drill is a P1 issue.
- **Monthly partial restore** — Restore of a single tenant's data to a sandbox tenant, validating GDPR erasure audit trail.
- **DR runbook** — Versioned in the repo (`docs/runbooks/dr.md`), owned by SRE, reviewed on every game day.

### Pod Disruption Budgets & Anti-Affinity

```yaml
# api PDB — at least 2 pods available during voluntary disruption
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels: { app: api }

---
# worker PDB — tolerate 25% drain; workers checkpoint safely
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: worker-pdb
spec:
  maxUnavailable: "25%"
  selector:
    matchLabels: { app: worker }
```

All long-lived application Deployments (`frontend`, `api`, `worker`, `worker-shadow`) use `topologySpreadConstraints` with `topologyKey: topology.kubernetes.io/zone` and `whenUnsatisfiable: DoNotSchedule`, plus `podAntiAffinity` preferring different nodes within a zone. Observability StatefulSets use equivalent zone-aware anti-affinity through their upstream chart values. This guarantees that no single AZ or node outage removes more than `1/3` of API or worker capacity.

### Database Scale & Connection Management

- **PgBouncer (transaction mode)** injected as a sidecar to `api`, `worker`, and `worker-shadow` pods. Application connections target PgBouncer; PgBouncer multiplexes onto a small number of real Postgres connections (typically 20–40).
- **Read-replica routing** — SQLAlchemy/`psycopg` session factories expose `get_read_session()` and `get_write_session()`. All dashboard, status, metering, and audit *read* paths use the replica; config writes, billing rollups, and metering inserts use the primary.
- **Statement timeouts** — All application roles enforce `SET statement_timeout = '30s'` at connection time; long-running admin queries go through a dedicated analyst role with higher timeout and strict audit.
- **Partitioning** — `llm_usage`, `audit_log`, `billing_rollup_hourly`, and `execution_runs` are partitioned by month. A scheduled job creates the next month's partition 7 days in advance.
- **Sharding headroom (v1 preparation)** — Tenant ID is included in the primary key of hot tables so a future move to a sharded topology (Citus / logical sharding) does not require schema redesign.

### Redis HA Configuration

- **Mode** — Redis Cluster (not standalone/Sentinel) with 3 primaries × 2 replicas across 3 AZs.
- **Persistence** — AOF (`appendfsync everysec`) + RDB snapshots; lost up to 1s of cache/queue state is acceptable.
- **Eviction** — `maxmemory-policy: noeviction` on the cluster namespace used by ARQ (queue must never silently drop jobs) and `allkeys-lru` on a separate cache namespace for idempotency keys and SSE fan-out.
- **Client retry** — All Redis clients use exponential backoff with jitter; a circuit breaker opens if cluster availability drops, surfacing a `/readyz` failure.

## Frontend

Single-page frontend for monitoring and administration. Vite + React + TypeScript on port 3000.
The UI should not look like a generic SaaS dashboard: the primary visual direction is pixel art, and the implementation target is to reproduce the Office View from [`johnkf5-ops/the-dev-squad`](https://github.com/johnkf5-ops/the-dev-squad) as faithfully as possible, minimizing interpretation during implementation.

### Access Model

- **Viewer** — Can access the dashboard, ticket/job status views, and SSE monitoring streams for their tenant/team.
- **Operator** — Viewer permissions plus approve/deny interrupts and retry failed jobs.
- **Admin** — Operator permissions plus agent config CRUD, graph editing, cost reports, and dry-run testing.
- **Super-admin** — Full access including tenant management and cross-tenant visibility.
- **Role enforcement** — JWT contains `role`, `tenant_id`, `team_ids` claims checked both in the frontend router and in FastAPI route dependencies. Frontend guards improve UX; backend checks remain authoritative.

### Features

- **Dashboard** — Real-time pipeline monitoring, ticket/job status, and SSE-backed execution updates for authenticated users, scoped to their tenant/team.
- **Pixel-art control room** — The main monitoring screen should replicate the visual grammar of the Dev Squad Office View as closely as possible: pixel-art room, visible agents, animated states, decorative props, and ambient motion communicating system status at a glance.
- **Parallel ticket processing** — v1 must support multiple independent tickets running concurrently under configured worker/model limits. The system-level fan-out is queue dispatch across workers; the fan-in is the monitoring/admin UI aggregating status for all active runs.
- **Break-glass interrupts** — v1 includes operator-controlled pause/approval points only for exception paths such as `security_review`, merge conflicts, budget exhaustion, or unresolved ambiguity. Routine successful runs should not pause for manual approval.
- **Agent Config CRUD** — Create/edit/delete agent config records used at startup. Each agent has: name, role, model, fallback model, system prompt, tools, and retry limits. Admin only.
- **Default OpenCode Go model mapping** — Every agent role starts with an OpenCode Go default model chosen for its workload profile, but admins can override the model per agent in configuration.
- **Fallback model configuration** — Every agent has a configurable fallback model from a different provider for automatic failover.
- **Role-scoped tool governance** — Agent configs must respect backend-enforced per-role tool whitelists so no role can be granted capabilities outside its operational boundary from the admin UI.
- **Custom sprite upload** — Admin users can upload/replace sprite assets and map them to UI roles/states without editing source code.
- **Agent Testing** — Send a test message to an agent and see the response before deploying. Admin only.
- **Dynamic graph rebuilding** — Graph definitions are edited as config and recompiled into the LangGraph runtime in v1.
- **Visual graph editor** — Admin users can edit nodes, edges, routes, and interrupt points from the UI instead of changing Python by hand.
- **Validation** — Validate model/tool names, graph topology, allowed handlers, edge routing, asset references, and role-specific tool whitelists before a config can be activated.
- **Graceful config activation** — Config changes compile and validate first. On activation, the system performs a rolling restart of workers. Updated configs apply only to new runs. In-flight or paused runs keep the pinned graph + agent config snapshot they started with and resume against that exact snapshot rather than hot-swapping topology mid-run.
- **Config versioning & rollback** — All config changes are versioned in PostgreSQL with audit trail. Admins can roll back to any previous config version.
- **Dead letter queue management** — Operators can view, inspect, retry, or dismiss DLQ entries from the admin UI.
- **Cost dashboard** — Real-time and historical LLM cost reporting by tenant, team, agent role, and model. Budget consumption gauges with alert thresholds.

### Visual Direction

- **Copy-first rule** — Treat `the-dev-squad` as the visual reference implementation, not just inspiration. Default to copying the same layout logic, scene composition, sprite treatment, prop density, and animation feel unless a direct copy conflicts with this product's information architecture.
- **Asset source** — Reuse the pixel-art assets from [`johnkf5-ops/the-dev-squad`](https://github.com/johnkf5-ops/the-dev-squad) directly whenever possible. Only create or adapt assets when the original art cannot represent LangGraph/Jira/GitHub-specific concepts.
- **Minimal translation** — Change labels, status semantics, and domain-specific props only where required to map the original "dev squad office" to this LangGraph/Jira/GitHub workflow. Do not reinterpret the art direction into a different style.
- **Implementation location** — Bundled reference art lives under `frontend/public/pixel-art/`. Tenant-uploaded or replaced sprites do not write into the container filesystem; they are stored durably in object storage and referenced through manifests.
- **Acceptance bar** — If a side-by-side comparison with `the-dev-squad` shows a materially different visual rhythm, spacing, animation behavior, or scene density, the implementation should be considered off-plan unless there is a documented product reason.

### Accessibility (WCAG 2.1 AA)

The pixel-art aesthetic imposes explicit accessibility obligations. The UI targets **WCAG 2.1 Level AA** conformance end-to-end.

- **Non-decorative content never depends on color alone.** Status (working, blocked, error) is communicated by icon + text + ARIA live region, not just sprite palette.
- **Text alternatives** — every sprite carries `role="img"` with a descriptive `aria-label` (e.g., "Planner agent reviewing ticket"). Decorative props use `aria-hidden="true"`.
- **Contrast** — text overlays and status labels maintain 4.5:1 contrast against their background, which may require a high-contrast text layer on top of the pixel-art scene.
- **Keyboard navigation** — all interactive elements are reachable via Tab in a logical order with a visible focus ring that is distinct from the pixel-art palette.
- **Motion sensitivity** — `prefers-reduced-motion` disables ambient animation loops and reduces status-change transitions to instantaneous state swaps. A user-controlled "reduced motion" toggle in account settings overrides the media query.
- **Screen reader narrative** — a visually-hidden live region announces pipeline state changes ("Ticket PROJ-123 moved from Coder to Tester") at a throttled cadence.
- **Zoom & reflow** — content remains usable at 200% zoom without horizontal scroll on 1280px viewports.
- **Axe-core + Pa11y in CI** — every PR to the frontend runs automated a11y tests; regressions block merge. Manual audits happen every milestone with at least one NVDA + VoiceOver pass.

### Internationalization (i18n)

- **Framework** — `react-intl` (FormatJS) with message extraction in CI. All user-visible strings are authored through `<FormattedMessage>` or `intl.formatMessage`.
- **v1 locales** — `en` (source) and `es` (reviewed by Spanish-speaking team). Additional locales added by translation vendor post-GA.
- **RTL readiness** — layout primitives use logical properties (`inline-start`/`block-start`); sprite scene direction is LTR-fixed but surrounding UI mirrors for RTL locales.
- **Date/number/currency** — all user-visible formatting routed through Intl APIs; timezones displayed with explicit zone labels.

### Animation Strategy

- **Animation fidelity first** — Reproduce the animation style from `the-dev-squad` as closely as possible instead of inventing new motion patterns.
- **Same motion categories** — Preserve the same kinds of ambient and stateful motion used by the reference UI: idle character motion, status-driven activity motion, environmental animation, and scene liveliness that prevents the office/control-room view from feeling static.
- **Same implementation bias** — Prefer the same technical approach used by the reference project for animation whenever feasible. If the reference uses sprite-driven or CSS-driven animation for a given element, keep that pattern here instead of replacing it with a different system.
- **Domain-only substitutions** — When an animation must change, the substitution should only swap the semantic meaning of the element, not the animation language. Example: a developer-at-desk activity can become an agent-processing-ticket activity, but the animation cadence and visual behavior should remain equivalent.
- **No silent simplification** — Static replacements for animated reference elements are out of scope unless the plan explicitly states that the original behavior cannot be ported.

### Agent Configuration Schema

```python
class AgentConfig(BaseModel):
    id: str                        # "coder", "planner"
    name: str                      # "Carlos", "Alexis"
    role: str                      # "coder", "planner", "tester", "reviewer", "pr_creator"
    model: str                     # LLM model ID, defaulting to role-based OpenCode Go mapping
    fallback_model: str | None     # automatic failover model from different provider
    system_prompt: str
    max_retries: int = 3
    tools: list[str]               # ["sandbox", "read_file", "git"]
    tool_policy: str = "role-scoped"  # cannot exceed backend role whitelist
    max_tokens_per_call: int | None = None   # None = derive from (role, model); see MODEL_TOKEN_CAPS

    # Config audit fields (populated by backend, not user-editable)
    version: int
    created_by: str                # OIDC subject
    created_at: datetime
    updated_at: datetime
```

Default role-to-model mapping for v1:

```python
DEFAULT_AGENT_MODELS = {
    "planner": {
        "primary": "opencode-go/glm-5",
        "fallback": "anthropic/claude-opus-4-7",
    },
    "coder": {
        "primary": "opencode-go/kimi-k2.5",
        "fallback": "anthropic/claude-sonnet-4-6",
    },
    "tester": {
        "primary": "opencode-go/minimax-m2.7",
        "fallback": "anthropic/claude-haiku-4-5-20251001",
    },
    "reviewer": {
        "primary": "opencode-go/glm-5",
        "fallback": "anthropic/claude-sonnet-4-6",
    },
    "pr_creator": {
        "primary": "opencode-go/minimax-m2.5",
        "fallback": "anthropic/claude-haiku-4-5-20251001",
    },
}

# Air-gapped deployments override fallbacks with self-hosted OpenCode Go models:
AIR_GAPPED_FALLBACKS = {
    "planner":    "opencode-go/glm-5-thinking",
    "coder":      "opencode-go/kimi-k2.5-instruct",
    "tester":     "opencode-go/minimax-m2.5",
    "reviewer":   "opencode-go/glm-5-thinking",
    "pr_creator": "opencode-go/minimax-m2.5",
}
```

If an agent config omits `model`, the backend should hydrate it from `DEFAULT_AGENT_MODELS[role]["primary"]`. If an admin explicitly sets a different model, that override wins as long as the provider/model string resolves in the pinned model catalogue. The `fallback_model` follows the same logic with `DEFAULT_AGENT_MODELS[role]["fallback"]` — or `AIR_GAPPED_FALLBACKS[role]` when the deployment profile is `air_gapped`.

#### Model Catalogue & Per-call Token Caps

`max_tokens_per_call` is not a single global number. Each entry in the pinned model catalogue declares its real context window and per-role input/output caps; the router enforces the minimum of (model ceiling, role cap, tenant override) before dispatching the call. A config referencing a model not in the catalogue fails validation.

```python
class ModelSpec(BaseModel):
    id: str                                # "opencode-go/glm-5", "anthropic/claude-sonnet-4-6"
    provider: str
    context_window_tokens: int             # hard ceiling from the provider
    max_output_tokens: int                  # hard ceiling on output
    supports_tool_calls: bool = True
    air_gapped_ok: bool = False             # True if deployable without external egress
    input_per_1k_usd: Decimal
    output_per_1k_usd: Decimal

# Per-role request ceilings. The router sends min(model.context_window, ROLE_CAP)
# of input tokens and min(model.max_output, ROLE_OUTPUT_CAP) of output.
ROLE_TOKEN_CAPS = {
    "planner":    {"input": 120_000, "output": 16_000},
    "coder":      {"input":  80_000, "output": 16_000},
    "tester":     {"input":  40_000, "output":  4_000},
    "reviewer":   {"input": 120_000, "output":  8_000},
    "pr_creator": {"input":  20_000, "output":  2_000},
}

def resolve_max_tokens(role: str, model: ModelSpec, tenant_override: int | None) -> tuple[int, int]:
    role_caps = ROLE_TOKEN_CAPS[role]
    in_cap = min(model.context_window_tokens, role_caps["input"])
    out_cap = min(model.max_output_tokens, role_caps["output"])
    if tenant_override is not None:
        in_cap = min(in_cap, tenant_override)
    return in_cap, out_cap
```

The catalogue is deployed as a Helm-rendered ConfigMap (`model-catalogue.yaml`) and hot-reloaded on `kill -HUP`; tenant-level overrides live in `tenants.model_overrides` and never raise caps above the catalogue.

### API Versioning & Deprecation Policy

All HTTP endpoints are versioned under `/api/v1/...`. Versioning applies to paths, request/response schemas, SSE event envelopes, webhook payload shapes produced by the backend, and metering export schemas.

- **Semver for the API surface** — a `v1` major prefix guarantees backwards compatibility for additive changes. Breaking changes require a new prefix (`/api/v2/...`) shipped in parallel.
- **OpenAPI contract** — generated from FastAPI route types on every build; schema diffs are gated in CI by `openapi-diff` to block accidental breaking changes.
- **Deprecation SLA** — deprecated endpoints/fields emit `Deprecation` and `Sunset` headers and a structured log. Minimum 6-month parallel support window before removal.
- **Client-visible SSE envelope versioning** — every SSE event carries `schema_version`; clients negotiate via `Accept-Version` header.
- **Graph compatibility epoch** — `compatibility_epoch` in `GraphConfig` is bumped only for changes that break checkpoint resume. When an epoch retires, existing runs at the old epoch are allowed to drain (non-terminal run duration cap of 14 days) before the old handler registry can be removed.
- **Metering/billing export schema** — versioned independently (`v1`, `v2`) with a minimum 12-month parallel support for finance integrations.

### API Endpoints

All endpoints below are prefixed with `/api/v1`.

| Method | Path | Purpose | Min Role |
|---|---|---|---|
| GET | /api/auth/login | Redirect to OIDC login | — |
| GET | /api/auth/callback | OIDC callback, create session | — |
| POST | /api/auth/logout | Revoke session + refresh token | viewer |
| POST | /api/auth/revoke-all | Revoke all sessions for current user | viewer |
| GET | /api/status/jobs/{run_id} | Get execution status for a specific run | viewer |
| GET | /api/status/jobs | List active/recent jobs | viewer |
| GET | /api/stream/jobs/{run_id} | SSE execution stream for a specific run | viewer |
| GET | /api/stream/jobs | SSE stream for global monitoring | viewer |
| GET | /api/status/jobs/{run_id}/approval | Get current approval/interrupt state | operator |
| POST | /api/status/jobs/{run_id}/approval | Approve, deny, or resume a paused run | operator |
| POST | /api/status/jobs/{run_id}/retry | Retry a failed/DLQ job | operator |
| GET | /api/admin/agents | List all agents | admin |
| GET | /api/admin/agents/{id} | Get agent config | admin |
| POST | /api/admin/agents | Create agent | admin |
| PUT | /api/admin/agents/{id} | Update agent | admin |
| DELETE | /api/admin/agents/{id} | Delete agent (blocked if in use) | admin |
| GET | /api/admin/agents/{id}/history | Get config change history for agent | admin |
| POST | /api/admin/agents/{id}/rollback/{version} | Roll back agent to previous version | admin |
| POST | /api/admin/agents/{id}/test | Test agent with sample input | admin |
| GET | /api/admin/graph | Get graph config | admin |
| PUT | /api/admin/graph | Update graph config | admin |
| GET | /api/admin/graph/history | Get graph config version history | admin |
| POST | /api/admin/graph/rollback/{version} | Roll back graph to previous version | admin |
| POST | /api/admin/graph/validate | Validate graph config | admin |
| POST | /api/admin/graph/compile | Compile + activate graph config | admin |
| GET | /api/admin/knowledge-bases | List configured knowledge bases and ingestion status | admin |
| POST | /api/admin/knowledge-bases | Create/update knowledge base metadata and source policy | admin |
| POST | /api/admin/knowledge-bases/{id}/ingest | Ingest or re-index approved documents into pgvector-backed storage | admin |
| POST | /api/admin/knowledge-bases/{id}/search | Dry-run semantic search with filters for relevance tuning | admin |
| POST | /api/admin/assets/sprites | Upload sprite asset | admin |
| GET | /api/admin/assets/sprites | List sprite assets/manifests | admin |
| PUT | /api/admin/assets/sprites/{id} | Update sprite metadata or role mapping | admin |
| DELETE | /api/admin/assets/sprites/{id} | Delete sprite asset (blocked if in use) | admin |
| GET | /api/admin/dlq | List dead letter queue entries | operator |
| GET | /api/admin/dlq/{id} | Get DLQ entry details | operator |
| POST | /api/admin/dlq/{id}/retry | Retry a DLQ entry | operator |
| DELETE | /api/admin/dlq/{id} | Dismiss a DLQ entry | operator |
| GET | /api/metering/usage | Get LLM usage/cost report | admin |
| GET | /api/metering/budget | Get budget status for tenant/team | admin |
| GET | /api/superadmin/tenants | List all tenants | super_admin |
| POST | /api/superadmin/tenants | Create tenant | super_admin |
| PUT | /api/superadmin/tenants/{id} | Update tenant | super_admin |
| GET | /api/superadmin/tenants/{id}/teams | List teams for tenant | super_admin |
| POST | /api/superadmin/tenants/{id}/teams | Create team | super_admin |
| PUT | /api/superadmin/tenants/{id}/teams/{team_id} | Update team | super_admin |
| POST | /api/superadmin/credentials | Create/rotate credential set | super_admin |
| GET | /api/superadmin/audit-log | Query audit log | super_admin |
| GET | /healthz | Liveness probe | — |
| GET | /readyz | Readiness probe (checks DB + Redis) | — |

All status/stream/admin endpoints are tenant-scoped via JWT claims. The backend rejects any request where the JWT `tenant_id` does not match the requested resource. `run_id` is the canonical execution identifier; `ticket_key` is retained only for search/filtering and “latest run” views.

### Storage

Agent configs, graph definitions, execution snapshots, sprite manifests, and optional knowledge-base metadata/chunks are stored in **PostgreSQL** with full versioning, audit trail, and transactional integrity. Uploaded sprite binaries are stored in durable S3-compatible object storage (for example S3 or MinIO), not in the frontend container filesystem. The system no longer uses JSON files on the filesystem for mutable runtime configuration:

```sql
-- Versioned config storage
CREATE TABLE config_entries (
    id          TEXT NOT NULL,           -- e.g. "agent:planner", "graph:default"
    kind        TEXT NOT NULL,           -- "agent", "graph", "sprite"
    tenant_id   TEXT NOT NULL,
    version     INTEGER NOT NULL,
    data        JSONB NOT NULL,          -- the actual config payload
    active      BOOLEAN NOT NULL DEFAULT FALSE,
    created_by  TEXT NOT NULL,           -- OIDC subject
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    comment     TEXT,                    -- optional change description
    PRIMARY KEY (id, tenant_id, version)
);

-- Only one active version per config per tenant
CREATE UNIQUE INDEX idx_config_active
    ON config_entries (id, tenant_id)
    WHERE active = TRUE;

-- Immutable audit log
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    actor       TEXT NOT NULL,           -- OIDC subject
    action      TEXT NOT NULL,           -- "create", "update", "delete", "activate", "rollback"
    resource    TEXT NOT NULL,           -- "agent:planner", "graph:default"
    old_version INTEGER,
    new_version INTEGER,
    diff        JSONB,                   -- JSON diff of changes
    ip_address  INET,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_tenant ON audit_log (tenant_id, created_at DESC);

-- Per-run immutable config snapshot used for resume compatibility
CREATE TABLE execution_runs (
    run_id               UUID PRIMARY KEY,
    tenant_id            TEXT NOT NULL,
    team_id              TEXT NOT NULL,
    ticket_key           TEXT NOT NULL,
    thread_id            TEXT NOT NULL UNIQUE,
    graph_config_id      TEXT NOT NULL,
    graph_config_version INTEGER NOT NULL,
    config_snapshot_id   UUID NOT NULL UNIQUE,
    status               TEXT NOT NULL,       -- "queued", "running", "paused", "completed", "failed"
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE config_snapshots (
    id                  UUID PRIMARY KEY,
    tenant_id           TEXT NOT NULL,
    run_id              UUID NOT NULL UNIQUE REFERENCES execution_runs(run_id),
    graph_config        JSONB NOT NULL,
    agent_configs       JSONB NOT NULL,
    budget_context      JSONB NOT NULL,
    compatibility_epoch INTEGER NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Uploaded sprite binary metadata. The blob itself lives in object storage.
CREATE TABLE sprite_assets (
    id          TEXT NOT NULL,
    tenant_id   TEXT NOT NULL,
    version     INTEGER NOT NULL,
    object_key  TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    mime_type   TEXT NOT NULL,
    width       INTEGER,
    height      INTEGER,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    active      BOOLEAN NOT NULL DEFAULT FALSE,
    created_by  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, tenant_id, version)
);

-- Optional internal knowledge base for pgvector-backed RAG
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_bases (
    id               UUID PRIMARY KEY,
    tenant_id        TEXT NOT NULL,
    name             TEXT NOT NULL,        -- "enterprise_patterns", "repo_docs", "runbooks"
    description      TEXT,
    source_scope     TEXT NOT NULL,        -- "global", "team", "repo"
    embedding_model  TEXT NOT NULL,
    embedding_dims   INTEGER NOT NULL,
    active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_by       TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, name)
);

-- Parent table holds everything except the embedding column; the embedding
-- lives in per-dimension child tables so tenants can enable knowledge bases
-- against embedding models with different dimensionalities (e.g. 768, 1024,
-- 1536, 3072) without schema migrations.
CREATE TABLE knowledge_chunks (
    id                BIGSERIAL PRIMARY KEY,
    tenant_id         TEXT NOT NULL,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    embedding_dims    INTEGER NOT NULL,    -- denormalised from knowledge_bases for partitioning
    repo_full_name    TEXT,
    source_uri        TEXT NOT NULL,
    source_type       TEXT NOT NULL,       -- "adr", "runbook", "markdown", "api_doc", "pattern"
    source_version    TEXT,
    visibility_scope  TEXT NOT NULL DEFAULT 'tenant',
    chunk_index       INTEGER NOT NULL,
    content           TEXT NOT NULL,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_sha256    TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, knowledge_base_id, source_uri, chunk_index, content_sha256)
) PARTITION BY LIST (embedding_dims);

-- One partition per supported embedding dimension. Operators add new
-- partitions when onboarding a new embedding model; ingestion refuses to
-- write into an unregistered dimension.
CREATE TABLE knowledge_chunks_d768 PARTITION OF knowledge_chunks
    FOR VALUES IN (768);
ALTER TABLE knowledge_chunks_d768
    ADD COLUMN embedding vector(768) NOT NULL;

CREATE TABLE knowledge_chunks_d1024 PARTITION OF knowledge_chunks
    FOR VALUES IN (1024);
ALTER TABLE knowledge_chunks_d1024
    ADD COLUMN embedding vector(1024) NOT NULL;

CREATE TABLE knowledge_chunks_d1536 PARTITION OF knowledge_chunks
    FOR VALUES IN (1536);
ALTER TABLE knowledge_chunks_d1536
    ADD COLUMN embedding vector(1536) NOT NULL;

CREATE TABLE knowledge_chunks_d3072 PARTITION OF knowledge_chunks
    FOR VALUES IN (3072);
ALTER TABLE knowledge_chunks_d3072
    ADD COLUMN embedding vector(3072) NOT NULL;

-- Shared lookup index at the parent (non-vector columns):
CREATE INDEX idx_knowledge_chunks_lookup
    ON knowledge_chunks (tenant_id, knowledge_base_id, source_type, repo_full_name, source_version);

-- HNSW indices are created per-partition because vector(N) dimensionality
-- must match the index definition:
CREATE INDEX idx_knowledge_chunks_d768_hnsw
    ON knowledge_chunks_d768 USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_knowledge_chunks_d1024_hnsw
    ON knowledge_chunks_d1024 USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_knowledge_chunks_d1536_hnsw
    ON knowledge_chunks_d1536 USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_knowledge_chunks_d3072_hnsw
    ON knowledge_chunks_d3072 USING hnsw (embedding vector_cosine_ops);

-- Optional IVFFlat tuning path for very large corpora (also per partition).
```

Config edits create a new version. Activation requires passing validation + compile. Rollback activates a previous version. The audit log is append-only and cannot be modified or deleted. Bundled reference art can still ship under `frontend/public/pixel-art/`, but tenant-uploaded sprites are served from object storage through the backend or edge cache so they survive pod restarts and multi-replica deployments.

When the optional knowledge base is enabled, retrieval follows standard SQL filtering plus pgvector ranking instead of a separate vector service. The query pins `embedding_dims` so PostgreSQL prunes to a single partition and uses its native HNSW index:

```sql
SELECT source_uri, source_type, repo_full_name, content, metadata
FROM knowledge_chunks
WHERE tenant_id = $1
  AND knowledge_base_id = $2
  AND embedding_dims = $3                     -- partition pruning
  AND (repo_full_name IS NULL OR repo_full_name = $4)
  AND visibility_scope IN ('tenant', 'repo')
ORDER BY embedding <=> $5
LIMIT 8;
```

This keeps tenant filtering, transactional ingestion, backups, and auditability inside the same PostgreSQL control plane already required by the orchestrator.

### Execution Identity & Resume Compatibility

- `ticket_key` is the business identity from Jira; `run_id` is the execution identity for one accepted webhook/job.
- every accepted execution receives a fresh `run_id` and therefore a fresh `thread_id = tenant_id:ticket_key:run_id`
- operator approvals and resumes reuse the same `run_id` and `thread_id`
- repeated Jira events for the same ticket never reuse a previous run's `thread_id`
- resumes must load `config_snapshot_id`, not the latest active config version
- a config version or handler contract cannot be garbage-collected while referenced by a non-terminal run snapshot

Checkpoint state and long-term memory are separate persisted concerns:

- `PostgresSaver` stores resumable execution state per `thread_id`, which is unique per `run_id`
- `PostgresStore` stores namespaced memory/context entries scoped by `(tenant_id, repo_full_name, ticket_key)`
- `config_snapshot_id` pins the exact graph + agent config versions used by the run
- approval payloads and interrupt metadata live in checkpointed graph state so runs can pause and resume safely across process restarts

### Webhook Security & Idempotency

Webhook intake applies layered defenses: transport (TLS + IP allowlist), authenticity (HMAC signature), freshness (timestamp window), uniqueness (idempotency), and throttling (per-ticket rate limit).

```python
async def handle_jira_webhook(request: Request, redis: Redis) -> Response:
    # 1. Source IP allowlist (optional per tenant; Jira publishes ranges)
    if not ip_allowlisted(request.client.host, tenant_ip_allowlist(tenant_hint)):
        raise HTTPException(403, "source_ip_not_allowed")

    # 2. HMAC signature (constant-time compare)
    raw = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not verify_hmac_sha256(raw, sig_header, secret_for_tenant(tenant_hint)):
        raise HTTPException(401, "invalid_signature")

    # 3. Replay protection — reject events older than 5 min
    ts_header = request.headers.get("X-Atlassian-Webhook-Timestamp", "")
    if abs(time.time() - int(ts_header)) > 300:
        raise HTTPException(401, "stale_timestamp")

    payload = json.loads(raw)
    webhook_id = request.headers.get("X-Atlassian-Webhook-ID", "")
    event_type = payload.get("webhookEvent", "")
    ticket_key = extract_ticket_key(payload)

    # 4. Per-ticket webhook flood protection
    rl = await rate_limiter.check(
        key=f"webhook:{tenant_hint}:{ticket_key}",
        config=WEBHOOK_PER_TICKET_LIMIT,
    )
    if not rl.allowed:
        return Response(status_code=429, headers={"Retry-After": str(rl.retry_after)})

    # 5. Idempotency key includes signature for cryptographic uniqueness
    sig_digest = hashlib.sha256(sig_header.encode()).hexdigest()
    idempotency_key = f"webhook:idem:{hashlib.sha256(
        f'{webhook_id}:{ticket_key}:{event_type}:{sig_digest}'.encode()
    ).hexdigest()}"

    is_new = await redis.set(idempotency_key, "1", nx=True, ex=86400)
    if not is_new:
        logger.info("Duplicate webhook deduplicated", extra={
            "ticket_key": ticket_key, "webhook_id": webhook_id,
        })
        return Response(status_code=200, content="deduplicated")

    # Proceed with tenant resolution and job enqueue
    ...
```

- **Tenant secrets** — each tenant has its own HMAC secret, rotated every 90 days; rotation allows a 24h overlap where both old and new secrets verify.
- **IP allowlist (optional)** — tenants with strict compliance requirements can pin their webhook source to a list of CIDRs (Jira/GitHub publish official ranges).
- **Timestamp window** — 5-minute replay window matches GitHub/Slack norms; events outside the window are rejected and logged (not deduplicated) so retries do not silently succeed.
- **Signature-hash in idempotency key** — an attacker replaying the body with a re-signed header still hits a unique idempotency key, preventing idempotency bypass via header manipulation.

### Interrupt Contract

Interrupt handling in v1 must follow the LangGraph checkpoint/resume model instead of an ad hoc pause flag. On the autonomous-first success path these interrupts stay dormant; they are activated only when the graph explicitly routes into an exception or approval-required branch:

1. Compile the graph with `interrupt_before=[...]` and a persistent `thread_id`
2. Invoke the graph until it pauses at the configured interrupt
3. Persist `approval_pending`, `approval_target`, `approval_payload`, and `paused_at_node` into `TicketState`
4. Surface the pending approval in the dashboard and the job-specific approval endpoint
5. Resume with the same `run_id` and `thread_id` using a structured resume command or deny path
6. Record the operator decision into state and append it to the event stream
7. Record the operator decision in the audit log with actor, timestamp, and rationale

Approval payloads must be JSON-serializable so they can safely survive checkpoint persistence and UI round-trips.

### Frontend Structure

```
frontend/
├── package.json
├── Dockerfile
├── nginx.conf
├── vite.config.ts
├── public/
│   └── pixel-art/                     # Imported/adapted external pixel art assets
└── src/
    ├── App.tsx                        # App shell
    ├── router.tsx                     # Dashboard + admin routes with role guards
    ├── lib/
    │   ├── api-client.ts              # FastAPI API client (with tenant headers)
    │   ├── auth-store.ts              # Session + role state (OIDC)
    │   ├── use-pipeline.ts            # SSE consumer hook (tenant-scoped)
    │   └── use-metering.ts            # Cost/usage display hook
    ├── pages/
    │   ├── login.tsx                  # OIDC redirect
    │   ├── dashboard.tsx              # Pixel-art control room
    │   ├── admin.tsx                  # Agent config, DLQ, sprites
    │   ├── graph-editor.tsx           # Visual graph editor
    │   └── cost-dashboard.tsx         # LLM cost/usage reporting
    └── components/                    # Shared UI components (details at implementation time)
```

### Frontend Dependencies

| Package | Purpose |
|---|---|
| react, react-dom ^19 | UI framework |
| react-router-dom ^7 | Routing |
| @radix-ui/* (dialog, select, tabs, switch, tooltip) | Accessible form primitives |
| lucide-react | Icons |
| tailwindcss ^4 | Styling |
| @tailwindcss/vite ^4 | Tailwind v4 Vite integration |
| recharts ^2 | Cost/usage charts |
| oidc-client-ts | OIDC PKCE flow |

## Observability

### Structured Logging

All backend components emit JSON-structured logs via `structlog`:

```python
import structlog

logger = structlog.get_logger()

# Every log entry includes:
# - timestamp (ISO 8601)
# - level
# - event (message)
# - trace_id (correlation across all operations for a ticket)
# - tenant_id
# - ticket_key (when available)
# - component (api, worker, sandbox, etc.)
# - pod_name (from K8s downward API)

logger.info(
    "job_started",
    trace_id=state["trace_id"],
    tenant_id=state["tenant_id"],
    ticket_key=state["ticket_key"],
    agent_role="planner",
    model="opencode-go/glm-5",
)
```

Logs are collected by the Kubernetes logging pipeline (Loki via Promtail, or Fluentd → Elasticsearch) and indexed by `tenant_id`, `trace_id`, and `ticket_key`.

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge, Info

# Business metrics
tickets_processed = Counter(
    "devsquad_tickets_total",
    "Total tickets processed",
    ["tenant_id", "team_id", "outcome"],  # outcome: "pr_created", "escalated", "budget_exhausted"
)
ticket_duration = Histogram(
    "devsquad_ticket_duration_seconds",
    "Time from webhook to PR/escalation",
    ["tenant_id", "outcome"],
    buckets=[60, 300, 600, 1200, 1800, 3600, 5400, 7200],
)
escalation_rate = Counter(
    "devsquad_escalations_total",
    "Total escalations by reason",
    ["tenant_id", "reason"],  # reason: "max_retries", "budget", "merge_conflict", "diff_too_large"
)

# LLM metrics
llm_invocations = Counter(
    "devsquad_llm_invocations_total",
    "LLM API calls",
    ["tenant_id", "provider", "model", "agent_role"],
)
llm_latency = Histogram(
    "devsquad_llm_latency_seconds",
    "LLM response latency",
    ["provider", "model"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
)
llm_cost = Counter(
    "devsquad_llm_cost_usd_total",
    "Cumulative LLM cost in USD",
    ["tenant_id", "team_id", "provider", "model", "agent_role"],
)
llm_tokens = Counter(
    "devsquad_llm_tokens_total",
    "Total tokens consumed",
    ["tenant_id", "direction", "provider"],  # direction: "input", "output"
)
team_monthly_budget = Gauge(
    "devsquad_team_budget_monthly_usd",
    "Configured monthly budget cap per team",
    ["tenant_id", "team_id"],
)

# Infrastructure metrics
active_jobs = Gauge(
    "devsquad_active_jobs",
    "Currently executing jobs per worker",
    ["pod_name"],
)
queue_depth = Gauge(
    "devsquad_queue_depth",
    "Pending jobs in ARQ queue",
)
dlq_size = Gauge(
    "devsquad_dlq_size",
    "Items in dead letter queue",
    ["tenant_id"],
)
sandbox_active = Gauge(
    "devsquad_sandboxes_active",
    "Active sandbox pods",
    ["tenant_id"],
)

# Circuit breaker
provider_health = Gauge(
    "devsquad_provider_health",
    "Provider circuit breaker status (1=healthy, 0=open)",
    ["provider"],
)
provider_failovers = Counter(
    "devsquad_provider_failovers_total",
    "Provider failover events",
    ["primary_provider", "fallback_provider"],
)
```

### Service Level Objectives (SLOs)

SLOs are the contract between the platform and its tenants. They drive release gates (error budget policy), alerting (burn-rate alerts), and capacity decisions.

| SLI | SLO | Measurement Window | Error Budget |
|---|---|---|---|
| Webhook intake availability (2xx for valid signed webhook) | 99.95% | 30-day rolling | 21m 36s / month |
| Status/stream API availability (excl. 401/403 auth failures) | 99.9% | 30-day rolling | 43m 12s / month |
| Webhook-to-first-agent-action latency (p95) | ≤ 10s | 30-day rolling | 5% of valid runs |
| Webhook-to-PR/escalation duration (p95) | ≤ 45 min | 30-day rolling | 5% of runs |
| Run success rate (PR created OR clean escalation) | ≥ 97% | 30-day rolling | 3% of runs |
| LLM provider router success (after failover) | ≥ 99.5% | 7-day rolling | 0.5% of calls |
| Checkpoint durability (no lost runs on pod/AZ loss) | 100% | 30-day rolling | 0 |
| SSE stream stability (disconnect < 60s) | 99% | 30-day rolling | 1% of streams |

**SLI exclusions.** The following responses are **not counted** as failures against the error budget because they reflect client/caller issues rather than service unavailability:

- `401 Unauthorized` and `403 Forbidden` on any endpoint (invalid/expired credentials, missing scope).
- `400` validation errors on admin/superadmin writes.
- Webhook intake responses where HMAC verification fails, timestamp is stale, or source IP is outside an allowlist — these are intentional rejections, not availability events. They are still metered separately (`devsquad_webhook_rejected_total{reason}`) and alerted on spike anomalies.
- `429 Too Many Requests` responses from the rate limiter — these are expected protective behaviour, reported on a separate fairness dashboard.

All other 5xx responses, timeouts, dependency failures (`/readyz` failing), and SSE disconnects > 60s count against the budget. A Prometheus recording rule materialises the numerator/denominator for each SLI with these exclusions applied so burn-rate alerts fire only on real service issues.

### Burn-Rate Alerting

Alerts page on **error budget burn rate**, not raw thresholds. This matches the Google SRE multi-window, multi-burn-rate pattern:

| Severity | Burn rate | Short window | Long window |
|---|---|---|---|
| Critical (page) | 14.4x | 5 min | 1 hour |
| Warning (ticket) | 6x | 30 min | 6 hours |
| Low (review) | 1x | 2 hours | 24 hours |

### Error Budget Policy

- **Budget > 50% remaining** — release velocity unchanged; no freeze.
- **Budget 10–50%** — non-essential launches pause; reliability fixes prioritized.
- **Budget < 10%** — code freeze for the affected surface until burn rate returns to healthy; only rollback and fix-forward for reliability allowed.
- **Budget exhausted** — incident; blameless postmortem required before the clock resets at next window.

The error budget status is published on the Operations Overview Grafana dashboard and is a required review item in every weekly engineering sync.

### Incident Response & Status Page

- **Severity model**
  - `SEV1` — customer-visible outage or data loss; pager alert, incident commander paged within 5 min.
  - `SEV2` — major degradation affecting a class of tenants; pager alert within 15 min.
  - `SEV3` — minor degradation, single tenant, workaround exists; ticket, next business day.
- **On-call** — 24/7 primary + secondary rotation via PagerDuty. Escalation policy: unacknowledged SEV1 escalates to secondary at 5 min, engineering manager at 15 min.
- **Runbooks** — Every alert in Alertmanager links to a runbook in `docs/runbooks/`. Runbooks are reviewed quarterly; missing/stale runbooks block the associated alert from being promoted to pager severity.
- **Public status page** — Statuspage-compatible endpoint publishes the health of: `api`, `worker`, `webhook_intake`, `sse_stream`, `llm_openai`, `llm_anthropic`, `llm_opencode`. Per-component state is derived from Prometheus rules.
- **Incident comms** — SEV1 requires an initial status post within 15 min, updates every 30 min, and a public postmortem within 5 business days.
- **Postmortems** — Blameless; template in `docs/runbooks/postmortem-template.md`. Action items are tracked to closure in the project backlog and reviewed monthly.
- **Game days** — Monthly chaos engineering exercise in staging; quarterly DR drill (see Disaster Recovery). Results feed runbook updates.

### Alerting Rules (Alertmanager)

```yaml
groups:
  - name: devsquad.rules
    rules:
      # All tickets failing for 30 minutes
      - alert: AllTicketsFailing
        expr: |
          rate(devsquad_tickets_total{outcome="escalated"}[30m])
          /
          rate(devsquad_tickets_total[30m])
          > 0.8
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: ">80% of tickets are escalating in the last 30 minutes"

      # Queue backing up
      - alert: QueueBacklogHigh
        expr: devsquad_queue_depth > 20
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "ARQ queue depth exceeds 20 pending jobs"

      # Provider circuit breaker open
      - alert: ProviderCircuitOpen
        expr: devsquad_provider_health == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "LLM provider {{ $labels.provider }} circuit breaker is open"

      # All providers down simultaneously — every configured provider breaker open
      - alert: AllProvidersDown
        expr: min(devsquad_provider_health) == 0 and count(devsquad_provider_health == 0) == count(devsquad_provider_health)
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "All LLM providers are unavailable — new runs will escalate; runbook: docs/runbooks/all-providers-down.md"

      # Budget threshold
      - alert: TeamBudgetWarning
        expr: |
          sum by (tenant_id, team_id) (devsquad_llm_cost_usd_total)
          /
          max by (tenant_id, team_id) (devsquad_team_budget_monthly_usd)
          > 0.8
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Team {{ $labels.team_id }} in tenant {{ $labels.tenant_id }} has consumed >80% of monthly budget"

      # DLQ growing
      - alert: DLQGrowing
        expr: devsquad_dlq_size > 5
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Dead letter queue has >5 unprocessed items"

      # Worker pod health
      - alert: WorkerPodsUnhealthy
        expr: kube_deployment_status_replicas_available{deployment="worker"} < 2
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Fewer than 2 worker pods available"

      # Sandbox cleanup failing
      - alert: OrphanedSandboxes
        expr: devsquad_sandboxes_active > 20
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "More than 20 active sandbox pods — possible cleanup failure"
```

### Health & Readiness Probes

```python
@router.get("/healthz")
async def liveness() -> dict:
    """Kubernetes liveness probe. Returns 200 if the process is alive."""
    return {"status": "ok"}

@router.get("/readyz")
async def readiness(
    db: AsyncConnection = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    """Kubernetes readiness probe. Checks downstream dependencies."""
    checks = {}

    # PostgreSQL
    try:
        await db.execute("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    return JSONResponse(
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=status_code,
    )
```

### Distributed Tracing (OpenTelemetry)

Every ticket execution generates a W3C `traceparent` at webhook intake. Traces follow OpenTelemetry semantic conventions and are exported via OTLP to Tempo, with LangSmith receiving a complementary LLM-focused trace view.

- **Instrumentation** — `opentelemetry-instrumentation` auto-instruments FastAPI, psycopg, redis, httpx, arq; custom spans wrap LangGraph node execution, tool invocations, sandbox lifecycle, and provider routing decisions.
- **Propagation** — W3C Trace Context headers propagate across HTTP calls; ARQ job payloads carry `traceparent` + `tracestate`; LangGraph checkpoints include the current span context so resumes reattach correctly.
- **Span taxonomy**
  - `webhook.ingest` → `queue.enqueue` → `worker.pickup`
  - `graph.node.{planner,coder,tester,reviewer,pr_creator,pre_pr_sync}`
  - `llm.call` (with `gen_ai.*` semantic attributes: provider, model, tokens, cost)
  - `sandbox.job` (K8s job name, exit code, runtime class)
  - `github.api.{branch,commit,push,pr}` / `jira.api.{ticket,comment,status}`
- **Sampling** — Tail-based: keep 100% of error traces and budget-exhausted runs; head-based 10% sampling for successful runs; always-on 100% for `admin_write` and `superadmin` endpoints.
- **Trace ↔ Log ↔ Metric correlation** — Every log line and Prometheus exemplar carries `trace_id` and `span_id`; Grafana explore links across all three signals.
- **PII scrubbing in spans** — A span processor redacts values matching secret/PII patterns before OTLP export; ticket bodies are replaced with content hashes + length.

### Grafana Dashboards (shipped as ConfigMaps)

| Dashboard | Key Panels |
|---|---|
| **Operations Overview** | Queue depth, active jobs, worker pod count, DLQ size, ticket throughput |
| **LLM Economics** | Cost per day/week/month by tenant/team/model, budget consumption, cost per ticket distribution |
| **Provider Health** | Circuit breaker status, latency p50/p95/p99 per provider, failover events, error rates |
| **Ticket Lifecycle** | Duration distribution, retry frequency, escalation reasons, success rate by ticket type |
| **Sandbox Health** | Active sandboxes, resource utilization, cleanup events, orphaned pod alerts |
| **Tenant Overview** | Per-tenant ticket volume, cost, escalation rate, active jobs |

## Data Retention & Compliance

### Retention Policy

| Data Category | Retention | Mechanism |
|---|---|---|
| LLM usage/metering | 12 months | PostgreSQL table partitioning (monthly) + partition drop |
| Checkpoint state | 30 days after job completion | Scheduled cleanup CronJob |
| Long-term memory (PostgresStore) | 6 months since last access | TTL-based eviction |
| Knowledge base chunks (optional pgvector RAG) | Until replaced, deactivated, or tenant deletion | Versioned PostgreSQL rows + explicit re-index/delete workflow |
| Audit log | 24 months (regulatory minimum) | Append-only, partition by month |
| Config versions | Indefinite (all versions kept) | No auto-deletion |
| Config snapshots / execution runs | 30 days after terminal state | Scheduled cleanup after run completion |
| Uploaded sprite binaries | Until replaced or tenant deletion | Object storage lifecycle + manifest reference checks |
| Structured logs | 90 days | Loki/Elasticsearch retention policy |
| Prometheus metrics | 30 days (raw), 12 months (aggregated) | Thanos/Cortex downsampling |
| Sandbox artifacts | Deleted on job completion | Ephemeral volumes + cleanup CronJob |
| Dead letter queue | 30 days | Auto-expire with Redis TTL |

### GDPR & Compliance

| Concern | Mitigation |
|---|---|
| Source code in LLM context | Code is sent to LLM providers for processing. Tenants must approve the provider's DPA. Provider selection is per-tenant configurable. |
| PII in Jira tickets | Ticket content is processed by LLMs. The system does NOT store raw ticket content beyond the active checkpoint. Post-completion, only summary metadata is retained. |
| Right to erasure | Tenant deletion hard-deletes live tenant data: configs, checkpoints, memory, metering, sessions, credentials, sprite manifests, and sprite binaries. Immutable audit-log rows are retained only for their mandatory compliance window, but tenant/user identifiers are pseudonymized or tombstoned so the operational record survives without preserving live tenant data. |
| Data residency | LLM provider selection can be constrained per-tenant to providers with specific data residency guarantees (e.g., EU-only). |
| Credential handling | Credentials are encrypted at rest (AES-256-GCM), never logged, never included in LLM context, and rotatable without downtime. |
| Audit trail | All configuration changes, approval decisions, and administrative actions are recorded in an immutable audit log with actor, timestamp, and IP. |
| Data processing agreement | Each tenant must acknowledge the DPA for their configured LLM providers before the system processes their tickets. This acknowledgment is stored in tenant config. |

### Scheduled Cleanup CronJob

```python
class RetentionCleanup:
    """Runs as a Kubernetes CronJob every 6 hours."""

    async def run(self) -> None:
        # 1. Drop old metering partitions (> 12 months)
        await self.drop_old_metering_partitions()

        # 2. Delete completed checkpoint state (> 30 days)
        await self.cleanup_old_checkpoints()

        # 3. Evict stale memory entries (> 6 months since last access)
        await self.evict_stale_memory()

        # 4. Expire old DLQ entries (> 30 days)
        await self.expire_old_dlq()

        # 5. Log retention actions for audit
        logger.info("retention_cleanup_complete", **self.summary())
```

Sandbox garbage collection is intentionally handled by the separate `sandbox-cleanup` CronJob so operational cleanup cadence does not depend on the broader retention schedule.

## Key Design Decisions

1. **SSE over WebSocket** — Server-to-client push only. No bidirectional needed. `EventSource` auto-reconnects. Same FastAPI process, no extra infrastructure. Industry standard (OpenAI, Anthropic streaming use SSE).

2. **ARQ over BackgroundTasks** — Real concurrency control, separate worker process, job timeout, visibility into queue state. Enhanced with dead letter queue and graceful shutdown.

3. **Exit code for test pass/fail** — `exit_code == 0` from sandbox, not string matching on test output.

4. **Agents created once at module level** — Reused across invocations. Node functions wrapped with tenacity retry (3 attempts, exponential backoff) for transient API failures.

5. **Reviewer uses structured output** — Not `"APPROVED" in text.upper()`. Agent returns a structured response with `approved: bool` and `feedback: str`.

6. **Checkpointing at graph level only** — Sub-agents do not get their own checkpointer. The parent graph's PostgresSaver handles all persistence.

7. **Sandbox hardening** — gVisor runtime, non-root execution, resource limits, network policies with egress whitelist, ephemeral volumes, image scanning, and per-tenant namespace isolation.

8. **Memory namespacing** — Any `PostgresStore` usage must namespace by `(tenant_id, repo_full_name, ticket_key)` to prevent cross-tenant and cross-ticket contamination.

9. **Pinned compatibility window** — LangGraph and persistence packages stay within a tested major-version window to avoid silent API drift across orchestrator and worker images.

10. **Role-based access control (OIDC)** — Four-tier role hierarchy (viewer, operator, admin, super_admin) enforced via OIDC group mapping. Backend route dependencies enforce this even if the frontend guard is bypassed.

11. **Local-first context resolution** — Agents must consume Jira payload, local repo state, checkpointed state, optional internal pgvector-backed knowledge bases, and first-party metadata before falling back to external research. This reduces hallucination and keeps planning anchored to the actual repository and ticket.

12. **Least-privilege per agent** — Tool assignment is constrained by role whitelist rather than free-form configuration. A planner should not silently gain write/exec powers, and a coder should not silently gain PR/Jira authority.

13. **Spec-driven artifacts stay in state** — Constitution, feature spec, clarification log, implementation plan, task list, repo context, Jira context, optional knowledge retrieval summaries, and structured review findings are persisted in graph state so later nodes can reason over explicit SDD artifacts instead of reconstructing context from scratch.

14. **OpenCode Go defaults with multi-provider failover** — Every role has a default `opencode-go/*` model and an automatic fallback model from Anthropic or OpenAI. Circuit breakers trip after 5 consecutive failures and recover after 5 minutes.

15. **Config in PostgreSQL, not filesystem** — All configuration is versioned in PostgreSQL with audit trail, atomic writes, rollback capability, and consistency across all worker pods.

16. **Webhook idempotency** — SHA-256 deduplication via Redis with 24h TTL prevents duplicate processing of Jira webhooks.

17. **Merge conflict detection** — Pre-PR base branch sync detects drift and escalates on conflict instead of creating un-mergeable PRs.

18. **Diff size guard** — Oversized diffs (>2000 lines or >50 files) are escalated rather than sent to the reviewer, preventing context window overflow and low-quality reviews.

19. **Files changed deduplication** — `files_changed` uses a set-based reducer instead of append-only list, preventing duplicate entries across retries.

20. **Budget enforcement at every LLM call** — Hierarchical budget caps (per-ticket, per-team daily, per-team monthly) are checked before every invocation. Exhaustion triggers graceful escalation, not silent failure.

21. **Graceful shutdown** — Workers handle SIGTERM by draining active jobs to their next checkpoint boundary, preventing work loss during rolling updates.

22. **Dead letter queue** — Failed jobs are captured with full context for debugging. Operators can inspect, retry, or dismiss from the admin UI.

23. **Tenant credential isolation** — Credentials are encrypted, per-team, never in LLM context, and injected only at the service layer.

24. **Kubernetes-native from day one** — Helm charts, HPA, NetworkPolicies, ResourceQuotas, gVisor, health probes. Docker-compose retained only for local development.

25. **Envelope encryption with external KMS/Vault** — DEKs encrypt credentials, KEKs wrap DEKs in HSM-backed KMS or Vault. No plaintext secrets in Helm values, ConfigMaps, or container env. External Secrets Operator syncs references, not secrets.

26. **SLO-driven alerting with error budgets** — Alerts page on burn rate against defined SLOs, not raw thresholds. Error budget status gates release velocity.

27. **Progressive delivery with automated rollback** — Argo Rollouts canary (5→25→50→100) gated by Prometheus SLO analysis. Automated rollback on analysis failure within 2 min.

28. **Feature flags decouple deploy from release** — OpenFeature kill switches for LLM providers, PR creation, graph activation, and sandbox runtime. Release flags have mandatory cleanup SLAs.

29. **API versioned under /api/v1 with OpenAPI diff gates** — Breaking changes force a new major prefix; additive-only within a major. `openapi-diff` blocks accidental breaks in CI.

30. **Weighted-fair queue over raw ARQ FIFO** — Per-tenant queues with deficit round-robin + concurrency caps prevent noisy-neighbor starvation. Starvation promotion after 5 min.

31. **Expand/contract schema migrations** — Schema additions deploy before dependent code; destructive changes require two release cycles; every migration has a reversibility test.

32. **Prompt injection treated as a supply-chain risk** — Untrusted ticket/repo content is delimited and classified as data. Agent responses pass through secret/leak filters. Sensitive repo paths force a break-glass `security_review` interrupt, but routine tickets stay autonomous.

33. **Forbidden-path writeset + signed commits** — Agents cannot touch `main`, CI config, infra, secrets files, or CODEOWNERS. All agent commits are cosign-keyless signed; unsigned commits are rejected by branch protection.

34. **SBOM + signed images + SLSA provenance** — Every image ships with a CycloneDX SBOM, cosign signature, and SLSA attestation. Kubernetes admission rejects unsigned images.

35. **PgBouncer + read replica routing** — Application connections target PgBouncer (transaction mode); read paths route to a replica. Statement timeouts and partitioning keep hot tables manageable.

36. **Shadow mode for graph config activation** — New graph configs can replay real traffic in read-only shadow runs before activation, with gates on success-rate regression and cost inflation.

37. **GitHub App is the default identity** — Installation tokens minted on demand replace long-lived PATs. PAT is explicit opt-in with stricter limits and audit.

38. **WCAG 2.1 AA is non-negotiable** — Pixel-art aesthetic cannot regress accessibility. Axe-core + Pa11y run in CI; `prefers-reduced-motion` is honored end-to-end.

39. **Rate limiting is layered** — NGINX edge + FastAPI application + webhook-specific + LLM outbound + queue concurrency. Per-tenant overrides, 429 headers, Prometheus visibility.

40. **Blameless incident response with public status page** — SEV1/SEV2/SEV3 model, PagerDuty rotation, runbooks per alert, public statuspage, 5-business-day postmortem SLA.

41. **Optional RAG stays inside PostgreSQL via pgvector** — Internal semantic retrieval reuses the existing HA data plane, tenant filters, backups, and DR model instead of introducing a separate vector database for v1.

## Dependencies

Backend dependencies live in `backend/pyproject.toml`. Frontend dependencies live in `frontend/package.json`.

```toml
[project]
name = "dev-squad"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    # LangGraph + LLM
    "langgraph>=1.0,<2.0",
    "langgraph-checkpoint-postgres>=2.0,<3.0",
    "langchain>=0.3",
    "langchain-core>=0.3",
    "langchain-anthropic>=0.3",
    "langchain-openai>=0.3",
    "anthropic>=0.40",
    "openai>=1.60",

    # External services
    "jira>=3.8",
    "PyGithub>=2.4",
    "gitpython>=3.1",

    # Sandbox (Kubernetes API for job management)
    "kubernetes>=31.0",

    # API
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",

    # Queue
    "arq>=0.26",

    # Auth (OIDC)
    "authlib>=1.4",
    "httpx>=0.28",

    # Database
    "psycopg[binary,pool]>=3.2",
    "pgvector>=0.3",
    "alembic>=1.14",

    # Redis
    "redis>=5.0",

    # Observability
    "langsmith>=0.2",
    "structlog>=24.0",
    "prometheus-client>=0.21",

    # Resilience
    "tenacity>=9.0",

    # Config / validation
    "pydantic>=2.10",
    "pydantic-settings>=2.10",
    "python-dotenv>=1.1",

    # Encryption + secrets
    "cryptography>=44.0",
    "hvac>=2.3",                 # HashiCorp Vault client (optional, for Vault deployments)
    "boto3>=1.35",               # AWS KMS/Secrets Manager (optional, for AWS deployments)

    # Rate limiting
    "slowapi>=0.1.9",            # FastAPI rate limiting with Redis backend

    # Feature flags
    "openfeature-sdk>=0.7",

    # OpenTelemetry
    "opentelemetry-api>=1.27",
    "opentelemetry-sdk>=1.27",
    "opentelemetry-exporter-otlp>=1.27",
    "opentelemetry-instrumentation-fastapi>=0.48b0",
    "opentelemetry-instrumentation-httpx>=0.48b0",
    "opentelemetry-instrumentation-psycopg>=0.48b0",
    "opentelemetry-instrumentation-redis>=0.48b0",

    # Secret scanning (invoked as subprocess by diff guard)
    # gitleaks + trufflehog are shipped as binaries, not Python deps.

    # i18n (backend emits locale-aware messages)
    "babel>=2.16",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.8",
    "mypy>=1.13",
    "httpx>=0.28",           # for FastAPI test client
    "testcontainers>=4.0",   # for integration tests with real Postgres/Redis
    "faker>=30.0",           # for test data generation
    "hypothesis>=6.100",     # property-based + fuzz tests on parsers/validators
    "schemathesis>=3.30",    # OpenAPI-driven API fuzzing
]
```

## CI/CD & Release Engineering

### Pipeline Stages

Every commit flows through a deterministic pipeline. Promotion between stages requires all prior gates to pass.

| Stage | Gates | Artifacts |
|---|---|---|
| `pr-check` | Lint (ruff, mypy), unit tests, secret scan (gitleaks + trufflehog), dependency scan (Trivy/Grype/OSV), license scan, OpenAPI diff, a11y (Axe), type check frontend | Coverage report, scan reports |
| `build` | Image build (buildx) + SBOM (syft) + image signing (cosign keyless) + SLSA provenance | Signed images with digests, SBOMs |
| `integration` | Integration tests (testcontainers), migration apply + reverse, Helm render + kubeconform, policy checks (Kyverno/Conftest) | Test logs, rendered manifests |
| `staging-deploy` | Deploy to staging via ArgoCD, smoke tests, E2E against test repos | Staging URLs, E2E reports |
| `chaos-nightly` | Chaos tests on staging (LLM garbage, sandbox crash, DB loss, Redis partition, worker kill) | Chaos reports |
| `canary-prod` | Canary 5% → 25% → 50% → 100% with automated rollback on SLO burn | Canary deployment report |

### Progressive Delivery

- **Argo Rollouts (canary)** — API and worker Deployments use Argo Rollouts with step weights `5%, 25%, 50%, 100%` and automated analysis against Prometheus SLO queries (`error_rate < 0.5%`, `p95_latency < SLO`) over 10-minute windows per step.
- **Automated rollback** — any analysis failure reverts to the previous stable revision within 2 minutes.
- **Blue/green for frontend** — atomic swap of the NGINX-served artifact bundle; instant rollback by pointer flip.
- **Feature flags decouple deploy from release** — large features merge dark behind OpenFeature flags and are exposed progressively by tenant cohort.

### Database Migration Safety (expand / contract)

- **Additive first** — `alembic upgrade` deploys *before* the code that depends on new columns/tables. Deploys are two-step: (1) migrate schema, (2) roll out code.
- **Backfill concurrency** — data backfills run in batched background jobs with progress metrics; never in migration scripts.
- **No destructive migrations in one release** — dropping a column/table requires two releases: mark unused → drop after one full release cycle and verification that no running code references it.
- **Migration reversibility** — every migration has a `downgrade()` path tested in CI on a seeded DB.
- **Migration preview gate** — CI applies all pending migrations to a production-shaped snapshot and runs the prior release's test suite against the migrated schema to catch breaking changes.
- **Long-running migrations** — any migration expected to take > 30s runs with `SET lock_timeout` and is scheduled via a dedicated migration CronJob, not as part of the app pod startup.

### Rollback Strategy

- **Code rollback** — `kubectl argo rollouts undo` or ArgoCD re-sync to prior revision. Target: < 5 min.
- **Schema rollback** — forward-only by default; where reverse is supported, verified via the migration reversibility test.
- **Config rollback** — graph/agent config rollback via the versioned `config_entries` store (no redeploy required).
- **Credential rollback** — KEK rotation failures trigger a rollback to the prior KEK version; DEKs re-wrap under the previous KEK.
- **Rollback drills** — quarterly drill validates rollback time against SLO. Failed drills are P1 issues.

### Environment Parity

| Env | Purpose | Data | LLM providers |
|---|---|---|---|
| `dev` | Local Docker Compose | Seeded fixtures | Mocked |
| `ci` | CI ephemeral clusters | Synthetic | Mocked |
| `staging` | Pre-prod, mirrors prod topology | Synthetic + opt-in anonymized replay | Real providers, capped budget |
| `prod` | Customer traffic | Live | Real providers, tenant budgets |

All four environments share the same Helm chart with values overlays. Drift between staging and prod topology is a P2 issue.

### Feature Flags

- **Provider** — OpenFeature SDK with Unleash (self-hosted) as the default backend; LaunchDarkly supported for enterprise deployments.
- **Flag taxonomy** — `release-*` (temporary, ≤ 90 days), `ops-*` (long-lived kill switches), `experiment-*` (A/B).
- **Per-tenant targeting** — flags can be scoped by `tenant_id`, `team_id`, or `role`, enabling cohort rollouts.
- **Kill switches (mandatory for v1)** — `llm_provider_opencode`, `llm_provider_anthropic`, `llm_provider_openai`, `sandbox_gvisor`, `graph_activation_enabled`, `pr_creation_enabled`. Each lets operators disable a subsystem without a redeploy.
- **Lifecycle discipline** — release flags have a required cleanup ticket with a due date. Stale flags (> 90 days past due) trigger a weekly alert.
- **Audit** — every flag change is written to `audit_log` with actor and rationale.

## Testing Strategy

### Test Pyramid

| Level | Count Target | Scope | Runs |
|---|---|---|---|
| Unit | ~200+ | Individual functions, reducers, guards, routers | Every commit (CI) |
| Integration | ~50+ | Multi-component flows with real DB/Redis (testcontainers) | Every PR |
| E2E | ~15+ | Full webhook → PR flow against test repos | Nightly + pre-release |
| Chaos | ~10+ | Failure injection (LLM garbage, sandbox crash, DB loss) | Weekly + pre-release |
| Prompt Regression | ~20+ | Known-good prompt/response pairs via LangSmith evaluations | Every prompt/config change |

### Prompt Regression Testing

```python
class PromptRegressionSuite:
    """Ensures prompt changes don't silently degrade agent quality."""

    def __init__(self, evaluator: LangSmithEvaluator):
        self.evaluator = evaluator

    async def test_planner_output_structure(self):
        """Planner must produce plan with specific sections."""
        result = await self.evaluate_agent(
            role="planner",
            input_fixture="fixtures/planner_input_crud_ticket.json",
            expected_sections=["files_to_modify", "approach", "test_strategy"],
        )
        assert result.score >= 0.8, f"Planner quality dropped: {result.score}"

    async def test_reviewer_structured_output(self):
        """Reviewer must return valid structured output, not free text."""
        result = await self.evaluate_agent(
            role="reviewer",
            input_fixture="fixtures/reviewer_input_simple_change.json",
            expected_schema=ReviewOutput,
        )
        assert result.valid_schema, "Reviewer output did not match expected schema"
```

## Development Roadmap (6 months, 10 seniors)

### Month 1: Foundation (Weeks 1-4)

| Week | Track A (4 devs) | Track B (3 devs) | Track C (3 devs) |
|---|---|---|---|
| 1 | Project scaffolding, Helm chart skeleton, CI/CD pipeline w/ SBOM + cosign + SLSA | PostgreSQL schema (config, metering, audit, billing), Alembic setup w/ reversibility tests | OIDC integration, RBAC middleware, session management, OpenAPI /v1 scaffold |
| 2 | LangGraph core: state, graph compiler, default edges | ARQ worker w/ concurrency, graceful shutdown, DLQ, weighted-fair queue | Tenant/team models, envelope encryption (DEK/KEK), Vault/KMS client, External Secrets |
| 3 | Planner + Coder agents (basic), tool implementations, forbidden-path writeset | Sandbox as K8s Job with gVisor, network policies, Kyverno admission for signed images | Webhook intake with HMAC + timestamp replay + idempotency, tenant resolution |
| 4 | Tester + Reviewer agents, structured output, prompt-injection delimiter framing | Provider router, circuit breakers, basic metering, OpenTelemetry instrumentation | FastAPI routes: status, stream (SSE), health probes, rate limiting (slowapi + Redis) |

**Month 1 Milestone:** Core pipeline processes a test ticket end-to-end on Kubernetes (single tenant, OIDC auth, signed images, envelope-encrypted credentials, no UI).

### Month 2: Production Hardening (Weeks 5-8)

| Week | Track A (4 devs) | Track B (3 devs) | Track C (3 devs) |
|---|---|---|---|
| 5 | PR Creator agent, merge conflict detection, diff guard, PR body sanitizer + gitleaks | Budget enforcement (all tiers), token metering, billing rollups + rate cards | Frontend scaffolding: Vite + React + router + OIDC login + i18n baseline |
| 6 | Full retry loop with budget gates, escalation paths, GitHub App installation flow | HPA for workers, resource quotas per tenant, sandbox cleanup CronJob, PodDisruptionBudgets + multi-AZ spread | Dashboard page: SSE-backed job status (tenant-scoped) + a11y primitives |
| 7 | Checkpoint resume testing, multi-worker parallelism, fair queue load test | Structured logging (structlog + PII scrub), Prometheus metrics, OTLP → Tempo, health probes | Admin page: agent config CRUD with validation + feature-flag integration |
| 8 | Integration test suite (testcontainers), E2E test skeleton, shadow-mode harness | SLO recording rules, burn-rate alerts, Alertmanager rules, Grafana dashboards (ConfigMaps), status page endpoint | Admin page: DLQ viewer, cost reporting basics, billing export UI (super_admin) |

**Month 2 Milestone:** Multi-tenant pipeline with budget caps, SLO-driven observability, progressive-delivery pipeline, and a basic functional UI meeting a11y baseline.

### Month 3: UI & Graph Editor (Weeks 9-12)

| Week | Track A (4 devs) | Track B (3 devs) | Track C (3 devs) |
|---|---|---|---|
| 9 | Config versioning + rollback API, audit log queries, Argo Rollouts canary wired up | Pixel-art asset import, sprite engine foundation, Axe/Pa11y in CI | Graph editor: node/edge CRUD UI, validation feedback |
| 10 | Agent dry-run/test API, prompt regression test framework, graph shadow-mode runner | Office View: room layout, agent sprites, basic positioning, reduced-motion support | Graph editor: conditional routes, interrupt points, compile/activate + shadow gate |
| 11 | Chaos test suite (LLM garbage, sandbox crash, DB loss, Vault outage, AZ failure) | Office View: agent animations (idle, working, error states) | Sprite upload UI, role/state mapping, asset management |
| 12 | E2E test suite completion, staging environment validation, fuzz tests (schemathesis + hypothesis) | Office View: ambient animations, props, scene liveliness | Cost dashboard + billing export UI + rate-card manager |

**Month 3 Milestone:** Full UI with pixel-art control room, visual graph editor with shadow mode, and config management. Staging environment running behind SLO-gated canary with automated rollback.

### Month 4: Polish & Scale Testing (Weeks 13-16)

| Week | Track A (4 devs) | Track B (3 devs) | Track C (3 devs) |
|---|---|---|---|
| 13 | Load testing: 50 concurrent tickets, worker autoscaling validation, PgBouncer tuning | Office View: real-time SSE integration, animated status transitions | Tenant management UI (super-admin), credential rotation flow + KEK rotation drill |
| 14 | Provider failover E2E, circuit breaker tuning, multi-provider testing, prompt-injection red team | Office View: acceptance comparison with reference project | RBAC edge cases, cross-tenant isolation audit, third-party security review |
| 15 | Performance optimization: DB query tuning, read-replica routing, Redis pipeline usage | Animation polish: timing, transitions, prop density, WCAG AA conformance sign-off | Audit log viewer, config diff visualization, break-glass UI |
| 16 | Data retention testing, partition management, cleanup verification, DR restore drill | Frontend accessibility audit (NVDA + VoiceOver), responsive layout, i18n ES locale | Documentation: API docs, admin guide, runbooks, SOC 2 control matrix, DPA template |

**Month 4 Milestone:** Scale-tested to 50 concurrent tickets. Pixel-art UI matches reference quality. External security review + DR drill passed.

### Month 5: Hardening & Beta (Weeks 17-20)

| Week | Track A (4 devs) | Track B (3 devs) | Track C (3 devs) |
|---|---|---|---|
| 17 | Beta deployment with 2-3 internal teams, feedback collection, SLO monitoring | Frontend bug fixes, animation refinements from beta feedback | On-call rotation live (PagerDuty), runbook validation per alert |
| 18 | Bug fixes from beta, edge case handling, error message improvements | Custom sprite upload workflow polish, asset validation | PagerDuty/Slack integration, public status page live, incident comms rehearsal |
| 19 | Chaos testing against beta environment, failure recovery validation, AZ failover drill | Graph editor UX improvements from beta feedback, shadow-mode UX polish | Backup/restore game day, PITR restore drill, ransomware-scenario drill |
| 20 | Performance regression testing, cost model validation with real data, billing reconciliation | Final visual QA against reference project, a11y audit pass #2 | Compliance documentation, DPA templates, SOC 2 readiness review |

**Month 5 Milestone:** Beta running with real teams and real tickets. SLOs measured against real traffic. DR + on-call drills passed. All critical bugs resolved.

### Month 6: GA Preparation (Weeks 21-24)

| Week | Track A (4 devs) | Track B (3 devs) | Track C (3 devs) |
|---|---|---|---|
| 21 | Production environment setup, infrastructure hardening, Kyverno admission enforced | Frontend final polish, loading states, error boundaries, final a11y pass | User onboarding flow, team self-service, GitHub App install wizard |
| 22 | Canary rollout playbook, rollback drill in prod-shaped env, feature-flag rollout plan | End-user documentation, video walkthroughs (captioned for a11y) | Customer-facing SLA, uptime monitoring, status-page subscription flow |
| 23 | Production load testing, capacity planning for 1000-dev org, cost projection validation | Final acceptance testing against all v1 scope items | Third-party pen test + remediation, SOC 2 Type I readiness |
| 24 | GA release, production deployment, canary through to 100%, monitoring validation | Post-launch monitoring, hotfix readiness, on-call warm handover | Retrospective, blameless postmortem review, v2 roadmap planning |

**Month 6 Milestone:** General Availability. Production deployment serving 1000-dev organization behind SLO-gated canary, public status page, signed-image admission, and full runbook coverage.

## Required Scope (v1)

The v1 scope is split into two tiers so schedule pressure never silently erodes the non-negotiable ones. Both tiers are committed for GA; the difference is in how they are defended under schedule stress.

### Tier 1 — GA-Blocking (ship is blocked if any of these slip)

Safety, correctness, security, and operability controls without which self-hosted customers cannot run the product. These cannot be deferred or partially shipped.

- **Parallel ticket processing** — multiple concurrent tickets across horizontally-scaled workers with aggregated monitoring.
- **Kubernetes-native deployment** — Helm charts, HPA, health probes, and gVisor sandboxes. Docker-compose is for local dev only.
- **Multi-tenancy** — tenant/team isolation with credential, data, and budget boundaries enforced at every query path.
- **OIDC authentication + four-tier RBAC** — enterprise IdP integration; backend enforcement is authoritative.
- **LLM budget governance with atomic reservations** — per-ticket, per-team daily, per-team monthly caps with race-free Redis reservations.
- **Provider failover with Redis-shared circuit breaker** — pool-wide breaker state; automatic fallback to a second provider (or self-hosted model in air-gapped profile).
- **Sandbox hardening** — gVisor runtime, per-tenant namespaces, NetworkPolicy egress whitelist, resource quotas.
- **Envelope encryption + external KMS/Vault** — DEK/KEK with HSM-backed keys, ESO-delivered; no plaintext secrets in cluster state.
- **GitHub App enforcement** — default installation tokens; PAT only as explicit opt-in with stricter limits.
- **Webhook security** — HMAC verification, timestamp freshness, idempotency, per-ticket rate limit, optional per-tenant IP allowlist.
- **Merge conflict detection** — pre-PR base branch sync; escalate on conflict.
- **Diff size guard** — escalate oversized diffs instead of sending them to the reviewer.
- **Forbidden-path writeset** — backend blocks agent modification of `main`, CI config, infra, Dockerfiles, secrets, and CODEOWNERS.
- **Signed commits + branch protection verification** — cosign-sign every agent commit; refuse PRs to unprotected base branches.
- **Prompt injection defenses** — delimited input frames, output leak classifier, forced `security_review` on sensitive paths.
- **Secret scanning end-to-end** — gitleaks + trufflehog pre-commit, in CI, and after every Coder node.
- **Supply chain security** — SBOM (syft), cosign keyless signing, SLSA provenance, Kubernetes admission rejecting unsigned images.
- **Config in PostgreSQL + shadow mode** — versioned config with audit trail, rollback, and shadow dry-run before activation.
- **Expand/contract migrations + reversibility tests** — additive-first with tested downgrades; destructive changes span two releases.
- **Observability stack** — structured logging (PII-scrubbed), Prometheus metrics, Grafana dashboards, Alertmanager, health probes, OTLP tracing.
- **SLOs + burn-rate alerting + error-budget policy** — formal SLOs with multi-window burn-rate alerts gating release velocity.
- **Disaster recovery** — defined RPO/RTO, multi-AZ deployment, PITR backups, PodDisruptionBudgets, quarterly restore drills.
- **Progressive delivery with automated rollback** — Argo Rollouts canary gated by Prometheus SLO analysis.
- **Rate limiting + weighted-fair queueing** — layered rate limits, per-tenant deficit round-robin, starvation protection.
- **Feature-flag kill switches** — LLM providers, PR creation, graph activation, sandbox runtime toggled without redeploy.
- **API /v1 + OpenAPI diff gate** — published schema, diff-gated in CI, 6-month deprecation policy.
- **Dead letter queue** — failed jobs captured with admin visibility and retry capability.
- **Data retention + GDPR compliance** — automated retention per category, tenant deletion cascade, DPA acknowledgment.
- **Graceful shutdown** — workers drain to checkpoint on SIGTERM.
- **Credential rotation SLA + break-glass** — 90-day rotation, alerts, dual-control emergency access, tested KEK rotation.
- **Self-host deployment modes** — `connected` and `air_gapped` profiles both validated; air-gapped has no external LLM egress.
- **Comprehensive testing** — unit, integration, E2E, chaos (including all-providers-down and Vault-unavailable), fuzz, prompt regression.
- **Public status page + incident runbooks** — status endpoint plus a runbook for every paging alert.

### Tier 2 — GA-Target (ship aim; may ship GA in a degraded form if schedule slips, must reach parity within one post-GA minor)

High-value differentiators and polish items. A defensible degradation path is documented for each so GA is not blocked if schedule pressure hits — but Tier 2 parity is tracked as a hard commitment after GA.

- **Spec-driven artifact lifecycle (full autonomous clarify loop)** — GA-target: full multi-round clarify with persisted artifacts. **Degradation**: ship constitution + feature_spec + plan + task_list, with clarify collapsed to a single pass (no iterative refinement). Hitting iteration cap still escalates.
- **Visual graph editor** — GA-target: node/edge/route/interrupt CRUD with live validation. **Degradation**: ship read-only visualisation + JSON config import/export; editing stays in source for early GA customers.
- **Custom sprite upload** — GA-target: admin upload, role/state mapping, object-storage persistence. **Degradation**: bundled sprites only; upload endpoint returns 501.
- **Pixel-art control room (full fidelity)** — GA-target: faithful reproduction of `the-dev-squad` Office View with all animation categories. **Degradation**: functional dashboard with a reduced-motion pixel-art skin; full scene deferred to minor release.
- **Billing export + rate-card reconciliation** — GA-target: hourly rollups, versioned rate cards, export endpoints, nightly reconciliation. **Degradation**: hourly rollups + CSV export only; reconciliation becomes a manual script run by ops.
- **Internationalisation (ES locale)** — GA-target: full `es` translation reviewed. **Degradation**: English-only with message extraction wired so ES can land post-GA.
- **Optional internal RAG (pgvector)** — GA-target: ingestion, retrieval, admin UI, role whitelist. Already feature-flagged off by default; degradation is simply keeping the flag off at GA.
- **WCAG 2.1 AA end-to-end** — GA-target: Axe/Pa11y in CI, NVDA + VoiceOver manual passes, full keyboard nav. **Non-negotiable subset (promoted to Tier 1)**: no color-only state, keyboard reachability of all interactive elements, `prefers-reduced-motion`, contrast AA on all text. Remaining AA items can finish during early GA but block the minor after.

**Schedule governance** — the weekly engineering sync reviews both tiers against burn-down. A Tier 1 slip is a P1 escalation to leadership with scope reduction required elsewhere. A Tier 2 slip triggers the documented degradation plan plus a dated parity ticket.

## Optional Extensions (v1-compatible, feature-flagged)

- **Internal RAG via `pgvector`** — Tenants may enable semantic retrieval over enterprise patterns, runbooks, and local technical docs stored in PostgreSQL. This is optional, off by default, and must remain tenant-scoped and read-only during ticket execution.
- **RAG retrieval policy** — `planner` and `reviewer` are the default consumers. `coder` may receive retrieved context or query it directly only when the tenant enables the capability and the role whitelist allows `knowledge-base read`.
- **Operational boundary** — Optional RAG must not introduce a new production datastore in v1; it reuses PostgreSQL HA, PgBouncer, backups, auditability, and retention controls already required by the core system.
