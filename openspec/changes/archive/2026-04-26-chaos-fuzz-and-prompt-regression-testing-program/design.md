# Design: Chaos, Fuzz, And Prompt Regression Testing

## Context

Quality engineering has a spec, but the concrete harness and CI cadence are missing. Without them, the persistence, routing, and sandbox protections cannot be continuously validated against realistic failure injection.

## Goals / Non-Goals

### Goals

- Deterministic chaos harness that injects each scenario.
- Contract-level and property-based fuzzing wired to CI.
- Prompt regression suite that catches planner and reviewer degradation.
- Monthly game-day cadence feeding operator practice.

### Non-Goals

- No vendor-hosted chaos service; everything runs inside the customer-owned CI or staging cluster.
- No production chaos by default; game-days target staging.

## Decisions

### Decision: Chaos via Kubernetes manipulations on ephemeral clusters

Each scenario is expressed as a pytest that bootstraps an ephemeral cluster (kind or k3d), deploys the Helm chart, injects the failure (kill pod, drop DB, partition Redis via iptables, scale down, etc), and asserts the expected observable behavior (circuit breaker opens, DLQ grows, graceful shutdown hits checkpoint, SLO burn-rate alert fires).

### Decision: Fuzz tools

`schemathesis` drives the OpenAPI for webhooks and admin API. `hypothesis` targets `GraphConfig` and routing rule functions. Both run against the same ephemeral stack used by integration tests.

### Decision: Prompt regression via LangSmith

LangSmith holds a fixtures dataset for planner and reviewer. A CI job runs evaluations with deterministic scoring (golden output match, structured metrics) and blocks on regression beyond tolerance.

### Decision: Nightly and monthly cadence

`chaos-nightly` runs the full chaos and fuzz suites. `prompt-regression` runs on every PR touching prompts or the planner/reviewer nodes, plus nightly. Monthly game-days replay the top-N scenarios with operator participation and produce a retrospective report.

## Risks / Trade-offs

- CI runtime. Mitigated by parallelization and nightly-only full runs.
- Flaky injection. Mitigated by deterministic setup and retries on known non-determinism points.
- Prompt fixture drift. Mitigated by versioned fixtures with retirement lifecycle.

## Migration Plan

1. Ship harness scaffolding and one scenario each (chaos, fuzz, prompt).
2. Expand to full PLAN.md list.
3. Wire nightly CI stage; soak for one release.
4. Start monthly game-days in staging.
