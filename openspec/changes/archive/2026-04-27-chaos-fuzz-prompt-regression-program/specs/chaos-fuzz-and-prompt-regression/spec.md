## ADDED Requirements

### Requirement: Chaos Suite Covers Tier 1 Failure Domains

The chaos suite SHALL include scenarios for at least: persistence outage, Redis split-brain, provider quota exhaustion, webhook flood, mid-traffic secret rotation, sandbox runtime crash, control-plane snapshot corruption, KEK rotation under load, network policy breach simulation, and DLQ overflow. Each scenario SHALL declare a deterministic seed, fault model, expected escalation reason, registered escalation sink, positive control, and recovery assertion.

#### Scenario: Scenario catalog includes reproducible metadata
- **WHEN** a maintainer opens `backend/tests/chaos/<area>/README.md`
- **THEN** each scenario lists its `scenario_id`, seed derivation, fault model, expected escalation reason, expected sink, positive control, and recovery assertion
- **AND** the expected sink is one of the registered escalation sinks, such as `ops://chaos`

#### Scenario: Persistence outage observes escalation
- **WHEN** the chaos persistence-outage scenario runs
- **THEN** the workflow surfaces a registered escalation reason consistent with the persistence outage runbook
- **AND** the run state shows the run terminating before any repo-writing node executes
- **AND** the recovered persistence layer contains the escalation record for triage

#### Scenario: Sandbox crash never bypasses guard
- **WHEN** the chaos sandbox-crash scenario runs
- **THEN** sandbox enforcement remains on
- **AND** the PR creator node is never reached
- **AND** the failure artifact names the sandbox runtime failure and seed

### Requirement: Fuzz Targets Cover All Public Inputs

Fuzz targets SHALL cover the webhook payload parser, Jira event normalizer, OpenAPI request bodies on the public API surface, escalation reason coercion, RAG retrieval inputs, billing CSV import, and admission exception payloads. Each target SHALL define its input shape, invariants, per-target budget, corpus path, and failure artifact format. Crashes SHALL be persisted to a checked-in corpus and shrunk to minimal repros.

#### Scenario: Fuzz target declares input shape
- **WHEN** a maintainer opens `backend/tests/fuzz/targets/<target>.md`
- **THEN** the target declares whether it uses Schemathesis, Hypothesis, or both
- **AND** it lists the generated input shape, invariants, corpus path, and maximum runtime budget

#### Scenario: New crash auto-archives shrunk repro
- **WHEN** a fuzz target finds a new crashing input
- **THEN** the shrunk repro is written to `corpora/<target>/crashes/`
- **AND** the test fails the run with the path of the crash artifact
- **AND** the artifact contains the seed, target id, minimized input, invariant violated, and local reproduction command

#### Scenario: Fuzz crash receives timely triage
- **WHEN** a new crash artifact is created
- **THEN** an item is routed to `ops://fuzz-triage`
- **AND** the item has a two-business-day triage SLA and a decision of `fix`, `fixture`, `by_design`, or `duplicate`

### Requirement: Prompt Regression Blocks Merge On Drift

The prompt regression suite SHALL include planner, coder, reviewer, escalation, role-boundary, and prompt-injection corpus suites. It SHALL run on every PR that modifies agent prompts, graph routing, governance code, runtime agent code, or prompt fixtures. A regression SHALL block merge and SHALL emit a diff artifact comparing the rendered prompt, recorded fixture, new output, and diverging assertion.

#### Scenario: Reviewer prompt drifts and blocks merge
- **WHEN** a PR changes the reviewer prompt and the new output diverges from the fixture
- **THEN** the suite fails
- **AND** the diff artifact contains the prompt, the recorded fixture, and the diverging assertion

#### Scenario: Role boundary probe blocks leakage
- **WHEN** a prompt-injection fixture attempts to make the reviewer run coder-only tools
- **THEN** the role-boundary suite fails if the reviewer output requests the coder-only action
- **AND** the failure routes to `ops://prompt-quality`

#### Scenario: Fixture refresh requires dual review
- **WHEN** a PR updates recorded prompt fixtures
- **THEN** the PR requires approval from one application owner and one security or operations reviewer
- **AND** the PR includes the fixture diff, refresh reason, model or runtime version, and air-gapped pass evidence

### Requirement: All Suites Are Air-Gapped Safe

Every chaos, fuzz, and prompt regression suite SHALL be runnable in the `air_gapped` profile with deterministic seeds and no vendor egress.

#### Scenario: Air-gapped CI runs the full ladder offline
- **WHEN** the `air_gapped` CI workflow runs the chaos, fuzz, and prompt regression suites
- **THEN** every scenario completes using local fixtures, deterministic seeds, and no outbound vendor network calls
- **AND** the workflow records the seed used per scenario in the run artifact

#### Scenario: Missing fixture fails closed offline
- **WHEN** an air-gapped prompt regression run cannot find a required recorded fixture
- **THEN** the suite fails with a fixture-missing error
- **AND** it does not attempt any live provider call

### Requirement: CI Triggers And Escalation Routing Are Codified

The CI topology SHALL run chaos on a nightly cron and on PRs labeled `chaos`, fuzz on a weekly cron and on PRs labeled `fuzz`, and prompt regression on every PR touching prompts, graph routing, governance code, runtime agent code, or fixtures. Failures SHALL route to registered escalation sinks without inventing new sink ids.

#### Scenario: PR opt-in labels run bounded suites
- **WHEN** a PR carries the `chaos` label
- **THEN** the bounded chaos suite runs with the configured 60 minute budget
- **AND** a failure uploads the chaos artifact and routes to `ops://chaos`

#### Scenario: Prompt regression is merge-blocking
- **WHEN** prompt regression fails on a pull request
- **THEN** the pull request remains blocked from merge
- **AND** the failure routes to `ops://prompt-quality` with the diff artifact attached
