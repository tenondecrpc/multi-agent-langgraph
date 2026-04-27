## ADDED Requirements

### Requirement: Chaos Suite Covers Tier 1 Failure Domains

The chaos suite SHALL include scenarios for at least: persistence outage, Redis split-brain, provider quota exhaustion, webhook flood, mid-traffic secret rotation, sandbox runtime crash, control-plane snapshot corruption, KEK rotation under load, and DLQ overflow. Each scenario SHALL declare the escalation reason it expects.

#### Scenario: Persistence outage observes escalation
- **WHEN** the chaos persistence-outage scenario runs
- **THEN** the workflow surfaces a registered escalation reason consistent with the persistence outage runbook
- **AND** the run state shows the run terminating before any repo-writing node executes

#### Scenario: Sandbox crash never bypasses guard
- **WHEN** the chaos sandbox-crash scenario runs
- **THEN** sandbox enforcement remains on
- **AND** the PR creator node is never reached

### Requirement: Fuzz Targets Cover All Public Inputs

Fuzz targets SHALL cover the webhook payload parser, Jira event normalizer, OpenAPI request bodies on the public API surface, escalation reason coercion, RAG retrieval inputs, billing CSV import, and admission exception payloads. Crashes SHALL be persisted to a checked-in corpus and shrunk to minimal repros.

#### Scenario: New crash auto-archives shrunk repro
- **WHEN** a fuzz target finds a new crashing input
- **THEN** the shrunk repro is written to `corpora/<target>/crashes/`
- **AND** the test fails the run with the path of the crash artifact

### Requirement: Prompt Regression Blocks Merge On Drift

The prompt regression suite SHALL run on every PR that modifies agent prompts, graph routing, or governance code. A regression SHALL block merge and SHALL emit a diff artifact comparing the recorded fixture and the new output.

#### Scenario: Reviewer prompt drifts and blocks merge
- **WHEN** a PR changes the reviewer prompt and the new output diverges from the fixture
- **THEN** the suite fails
- **AND** the diff artifact contains the prompt, the recorded fixture, and the diverging assertion

### Requirement: All Suites Are Air-Gapped Safe

Every chaos, fuzz, and prompt regression suite SHALL be runnable in the `air_gapped` profile with deterministic seeds and no vendor egress.

#### Scenario: Air-gapped CI runs the full ladder offline
- **WHEN** the `air_gapped` CI workflow runs the chaos, fuzz, and prompt regression suites
- **THEN** every scenario completes using local fixtures, deterministic seeds, and no outbound vendor network calls
- **AND** the workflow records the seed used per scenario in the run artifact
