## Architecture Reuse

- Reuse `pytest`, `hypothesis` (already declared in `backend/pyproject.toml`), and `schemathesis` (already declared) instead of introducing new frameworks.
- Reuse the existing `.github/workflows/chaos-nightly.yml` and `prompt-regression.yml` skeletons; this change defines what they execute.
- Reuse the existing escalation sink registry; chaos failures map to `ops://chaos`, prompt regressions to `ops://prompt-quality`, fuzz crashes to `ops://fuzz-triage`.
- Reuse the current contract-heavy test base without duplicating it. Contract tests keep validating API and workflow invariants; this layer validates behavior under injected faults, malformed input, and prompt or role-boundary drift.

## Suite Layout

```
backend/tests/
  chaos/
    persistence/
    redis/
    providers/
    webhook/
    secrets/
    sandbox/
    control_plane/
  fuzz/
    targets/
    corpora/
  prompt_regression/
    planner/
    coder/
    reviewer/
    injection/
    fixtures/
```

Each suite directory contains a `README.md` describing the scenario, the seed source, the expected escalation reason, and the recovery contract.

## Chaos Scenario Catalog

Each chaos scenario is identified by `<area>/<scenario_id>` and records `seed`, `fault_model`, `expected_escalation_reason`, `expected_sink`, `positive_control`, and `recovery_assertion`.

| Path | Fault model | Expected escalation reason | Recovery assertion |
|------|-------------|----------------------------|--------------------|
| `chaos/persistence/persistence_outage` | PostgreSQL primary unavailable during checkpoint save | `persistence_unavailable` | Run stops before repo write and persists escalation to `ops://chaos` after storage recovers |
| `chaos/redis/redis_split_brain` | Redis cluster partition with duplicate job delivery | `queue_partition_detected` | PostgreSQL idempotency rejects duplicates and DLQ rows remain durable |
| `chaos/providers/provider_quota_exhaustion` | Primary and fallback providers return quota exhaustion | `provider_capacity_exhausted` | Redis-shared circuit breaker opens and no role proceeds past routing guard |
| `chaos/webhook/webhook_flood` | Burst of duplicated Jira webhook payloads | `webhook_rate_limited` | Rate limiter and idempotency guard preserve one accepted event per delivery key |
| `chaos/secrets/mid_traffic_secret_rotation` | GitHub App and webhook secrets rotate while requests are in flight | `credential_rotation_incomplete` | Dual-secret window accepts valid old and new signatures, then converges to new secret only |
| `chaos/sandbox/sandbox_runtime_crash` | gVisor sandbox exits with a hard failure during test execution | `sandbox_runtime_failed` | Sandbox enforcement remains enabled and PR creation is unreachable |
| `chaos/control_plane/control_plane_snapshot_corruption` | Runtime graph config snapshot checksum fails | `config_snapshot_invalid` | Active config remains on last valid version and shadow validation records rejection |
| `chaos/secrets/kek_rotation_under_load` | KMS or Vault KEK rotation overlaps credential decrypt calls | `kek_rotation_blocked` | Decrypt failures fail closed and audit logs identify affected tenant and key version |
| `chaos/network/network_policy_breach` | Test workload attempts blocked egress from sandbox namespace | `network_policy_violation` | Egress remains denied and the event is routed to the registered policy sink |
| `chaos/control_plane/dlq_overflow` | DLQ exceeds configured backlog threshold | `dlq_capacity_exceeded` | Worker admission throttles new work and existing DLQ records remain queryable |

## Determinism And Air-Gapped Execution

- Chaos fault injection uses a deterministic seed. Each scenario records its seed in the failure artifact so reruns are reproducible.
- Prompt regression uses recorded model fixtures stored under `prompt_regression/fixtures/`. A live-provider mode is opt-in and only runs in connected CI; air-gapped runs must remain green using fixtures.
- Fuzz targets use `hypothesis` with a checked-in corpus. New crashes shrink to minimal repros and are committed.
- A missing seed defaults to the stable hash of `scenario_id`, `target_id`, or `fixture_id`. CI MAY override the seed, but it MUST print the resolved seed and write it to the artifact.
- Connected runs MUST NOT make vendor egress unless explicitly placed in live-provider mode. Air-gapped runs MUST use only fixtures, local OpenAPI documents, local corpora, and in-cluster dependencies.

## Fuzz Target Catalog

| Target | Input shape | Runner | Failure artifact |
|--------|-------------|--------|------------------|
| `webhook_payload` | Jira webhook JSON, signature headers, timestamp freshness, duplicate delivery key | Schemathesis plus Hypothesis strategies | Shrunk JSON body and normalized header map |
| `jira_event_normalizer` | Jira issue created, updated, transitioned, deleted, and comment events | Hypothesis | Minimal Jira event fixture |
| `openapi_public_inputs` | Public OpenAPI request bodies and query parameters for webhook, status, admin, and runtime APIs | Schemathesis | OpenAPI operation id, seed, request, and response |
| `escalation_reason_coercion` | Unknown, mixed-case, malformed, and oversized escalation reason strings | Hypothesis | Input string and coerced or rejected result |
| `rag_retrieval_inputs` | Tenant-scoped optional RAG query text, repository ids, and metadata filters | Hypothesis | Minimal query and tenant scope tuple |
| `billing_csv_import` | CSV rows, headers, encodings, decimal values, and malformed totals | Hypothesis | Minimal CSV file |
| `admission_exception_payloads` | Admission exception JSON for image, provenance, signature, and policy overrides | Schemathesis plus Hypothesis | Minimal exception payload and policy decision |

Crash artifacts live under `backend/tests/fuzz/corpora/<target>/crashes/<sha256>.json`. Each artifact includes the seed, minimized input, target id, invariant violated, stack trace summary, and local reproduction command. Deleted artifacts require a triage note explaining why the crash is unreachable or superseded.

The per-run budget is 30 minutes for the full weekly run and 10 minutes for PR opt-in label runs. A single target SHOULD receive a bounded share of the budget so one slow target cannot starve the corpus.

## Prompt Regression Catalog

| Suite | Fixtures | Merge behavior |
|-------|----------|----------------|
| `planner` | Clarification loops, spec readiness decisions, implementation plan generation, task list generation | Blocks merge on schema drift or missing readiness guard |
| `coder` | Repo-write gate probes, task execution prompts, forbidden path handling, test repair loops | Blocks merge on role leakage or write-before-ready behavior |
| `reviewer` | Security, tests, diff guard, forbidden path, and pre-PR sync review criteria | Blocks merge on missed mandatory rejection |
| `escalation` | Security review, budget exhaustion, ambiguity, merge conflict, and policy violation paths | Blocks merge when escalation reason or sink changes unexpectedly |
| `role_boundary` | Attempts to coerce planner, coder, tester, reviewer, or PR creator into another role action | Blocks merge on cross-role tool or privilege leakage |
| `prompt_injection` | Jira text, repo files, retrieved context, and fixture payloads containing instruction override attempts | Blocks merge on secret exposure, guard bypass, or privileged action |

Fixture refresh requires dual review from one application owner and one security or operations reviewer. The refresh PR MUST include the fixture diff, reason for change, model or runtime version, and confirmation that air-gapped fixtures still pass.

## CI Topology

| Suite              | Trigger                                                    | Budget                |
|--------------------|------------------------------------------------------------|-----------------------|
| Chaos nightly      | Nightly cron, plus PR label `chaos`                        | 60 min                |
| Fuzz weekly        | Weekly cron, plus PR label `fuzz`                          | 30 min                |
| Prompt regression  | Every PR touching prompts, graph routing, governance, runtime agent code, or fixtures | 10 min |

A failed chaos run opens an internal SEV3 ticket via the escalation sink. A prompt regression failure blocks merge and surfaces a diff artifact.

## Escalation And Triage

- Each chaos scenario declares the escalation reason it expects when its fault is injected. The test asserts the reason matches.
- Fuzz crashes are persisted to `corpora/<target>/crashes/` with a stable name derived from a hash of the input.
- Prompt regression diffs include the rendered prompt, the recorded fixture, the new fixture, and the diverging assertion.
- Chaos failures route to `ops://chaos` with severity `SEV3` unless an existing incident for the same scenario and seed is open.
- Fuzz crashes route to `ops://fuzz-triage` and have a two-business-day triage SLA. The triage decision is `fix`, `fixture`, `by_design`, or `duplicate`.
- Prompt regressions route to `ops://prompt-quality` and remain merge-blocking until the prompt, fixture, or assertion is corrected through dual review.

## Observability

- Metrics: `devsquad_chaos_scenarios_run_total`, `devsquad_chaos_failures_total{scenario}`, `devsquad_fuzz_crashes_total{target}`, `devsquad_prompt_regression_failures_total{suite}`.
- Alerts: chaos suite failure beyond a configured baseline, prompt regression failure on `main`, fuzz triage SLA breach.
- Additional labels: `tenant_id` only when safe for internal metrics, `deployment_profile`, `scenario`, `target`, `suite`, `seed_hash`, and `escalation_reason`.
- CI uploads `chaos-artifacts/`, `fuzz-artifacts/`, and `prompt-regression-artifacts/` for every failing run. Artifacts contain reproduction commands and omit secrets.

## Protected Workflow Invariants

- Chaos runs MUST exercise the existing escalation paths; they MUST NOT bypass the repo-write gate, test-then-review chain, or sandbox enforcement.
- Prompt regression MUST validate that role boundary prompts cannot be coerced into running other roles' actions.
- Fuzz targets that reach repo-writing code MUST assert `spec_ready_for_implementation` and task-list preconditions before any write-capable path is allowed.
- All suites MUST reference the registered escalation sinks. They MUST NOT invent new sink ids in tests or fixtures.

## Failure Modes

- Chaos test passes spuriously: scenario must include a positive control assertion.
- Prompt regression false positive on legitimate model upgrade: fixture refresh requires dual review.
- Fuzz crash unreachable from production code: triage process records a "by design" rationale before delete.
- Missing fixture in air-gapped mode: the suite fails closed with a fixture-missing error and does not call vendor APIs.
- Flaky scenario: quarantine requires an owner, expiry date, linked incident, and continued nightly reporting.
