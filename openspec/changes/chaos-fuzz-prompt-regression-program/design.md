## Architecture Reuse

- Reuse `pytest`, `hypothesis` (already declared in `backend/pyproject.toml`), and `schemathesis` (already declared) instead of introducing new frameworks.
- Reuse the existing `.github/workflows/chaos-nightly.yml` and `prompt-regression.yml` skeletons; this change defines what they execute.
- Reuse the existing escalation sink registry; chaos failures map to `ops://chaos`, prompt regressions to `ops://prompt-quality`, fuzz crashes to `ops://fuzz-triage`.

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

## Determinism And Air-Gapped Execution

- Chaos fault injection uses a deterministic seed. Each scenario records its seed in the failure artifact so reruns are reproducible.
- Prompt regression uses recorded model fixtures stored under `prompt_regression/fixtures/`. A live-provider mode is opt-in and only runs in connected CI; air-gapped runs must remain green using fixtures.
- Fuzz targets use `hypothesis` with a checked-in corpus. New crashes shrink to minimal repros and are committed.

## CI Topology

| Suite              | Trigger                                                    | Budget                |
|--------------------|------------------------------------------------------------|-----------------------|
| Chaos nightly      | Cron, plus PR label `chaos`                                | 60 min                |
| Fuzz weekly        | Cron, plus PR label `fuzz`                                 | 30 min                |
| Prompt regression  | Every PR touching `runtime/`, `governance/`, or fixtures   | 10 min                |

A failed chaos run opens an internal SEV3 ticket via the escalation sink. A prompt regression failure blocks merge and surfaces a diff artifact.

## Escalation And Triage

- Each chaos scenario declares the escalation reason it expects when its fault is injected. The test asserts the reason matches.
- Fuzz crashes are persisted to `corpora/<target>/crashes/` with a stable name derived from a hash of the input.
- Prompt regression diffs include the rendered prompt, the recorded fixture, the new fixture, and the diverging assertion.

## Observability

- Metrics: `devsquad_chaos_scenarios_run_total`, `devsquad_chaos_failures_total{scenario}`, `devsquad_fuzz_crashes_total{target}`, `devsquad_prompt_regression_failures_total{suite}`.
- Alerts: chaos suite failure beyond a configured baseline, prompt regression failure on `main`, fuzz triage SLA breach.

## Protected Workflow Invariants

- Chaos runs MUST exercise the existing escalation paths; they MUST NOT bypass the repo-write gate, test-then-review chain, or sandbox enforcement.
- Prompt regression MUST validate that role boundary prompts cannot be coerced into running other roles' actions.

## Failure Modes

- Chaos test passes spuriously: scenario must include a positive control assertion.
- Prompt regression false positive on legitimate model upgrade: fixture refresh requires dual review.
- Fuzz crash unreachable from production code: triage process records a "by design" rationale before delete.
