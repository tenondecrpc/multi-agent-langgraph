# autonomous-ticket-flow Specification

## Purpose
TBD - created by archiving change phase-1-runtime-sdd-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Protected Success Path

Any path that can reach PR creation MUST traverse planner-owned artifacts, implementation, test execution, review approval, and pre-PR sync.

#### Scenario: Successful run follows the mandatory sequence
- **WHEN** a ticket completes successfully
- **THEN** the run moves from planning into implementation only after the repo-write gate is satisfied
- **AND** every post-write path traverses tester, reviewer, and pre-PR sync before PR creation

#### Scenario: Invalid shortcut is rejected
- **WHEN** a workflow attempts to route directly from coder, tester, or reviewer to PR creation
- **THEN** the runtime rejects the route as invalid
- **AND** the run is blocked from creating a pull request

### Requirement: Retry And Escalation Boundaries

The runtime MUST bound clarification, testing, and review retries and MUST map every terminal failure to an explicit escalation reason and sink.

#### Scenario: Test retries remain bounded
- **WHEN** test execution fails and the configured retry budget remains
- **THEN** the run routes back to coder for another attempt
- **AND** it escalates when the retry budget is exhausted

#### Scenario: Review replan remains bounded
- **WHEN** the reviewer detects spec drift or missing decomposition
- **THEN** the run may route back to planner within the configured review and clarification limits
- **AND** it escalates when those limits are exhausted

### Requirement: Diff Size And Merge Guards

Oversized diffs and merge conflicts MUST be explicit guarded branches rather than informal reviewer judgment.

#### Scenario: Oversized diff escalates instead of flowing through review
- **WHEN** the changed file count or line count exceeds the configured diff thresholds
- **THEN** the run escalates with the recorded diff size details
- **AND** it does not continue to standard reviewer approval as if the diff were ordinary

#### Scenario: Base branch drift is checked before PR creation
- **WHEN** a run is approved for PR creation
- **THEN** the system compares the stored base branch head with the latest base branch head
- **AND** it escalates if the automated sync or rebase detects merge conflicts

### Requirement: Break-Glass Interrupts Stay Off The Normal Success Path

Manual approval MUST remain limited to registered exception paths such as security review, budget exhaustion, merge conflict, or unresolved ambiguity.

#### Scenario: Routine success does not pause for approval
- **WHEN** a run stays within policy and retry bounds
- **THEN** it proceeds without requiring a manual approval step on the normal success path

#### Scenario: Exception path creates an auditable interrupt
- **WHEN** the runtime routes to an interrupt-worthy exception path
- **THEN** the state records the paused node, approval payload, and escalation reason
- **AND** the later resume uses the same run identity and checkpoint lineage

### Requirement: Agent-Authored Tests Before PR Creation

The runtime MUST NOT mark a ticket as resolved or route to PR creation unless the coder has authored unit tests covering the changed or added logic and the run has executed an end-to-end test layer appropriate for the change, and both layers pass.

#### Scenario: Unit tests are authored alongside implementation
- **WHEN** the coder modifies or adds production logic for a ticket
- **THEN** the same run produces unit tests that exercise the changed behavior
- **AND** the tester executes those unit tests and records the result in state before review is allowed to approve

#### Scenario: End-to-end coverage gates user-facing changes
- **WHEN** a ticket introduces or modifies behavior reachable through a public API, webhook, UI surface, or cross-service flow
- **THEN** the run executes an end-to-end test that exercises that surface against the changed code
- **AND** the PR creator node refuses to open the pull request if the end-to-end layer was skipped or failed

#### Scenario: Missing or failing agent-authored tests block PR creation
- **WHEN** the task list declares required unit or end-to-end tests and any required layer is missing, skipped, or failing at review time
- **THEN** the run routes back to coder within the configured retry budget
- **AND** it escalates with an explicit `missing_or_failing_required_tests` reason when the retry budget is exhausted

#### Scenario: Failing tests iterate through the bounded tester-to-coder loop
- **WHEN** agent-authored unit tests or the declared end-to-end layer fail inside the sandbox
- **THEN** the graph follows the existing conditional edge back to coder using the same `max_test_retries` budget already declared for test failures
- **AND** each iteration re-runs coder, tester, and the required test layers against the same pinned artifacts until tests pass or the retry budget is exhausted
- **AND** the loop does not route to reviewer or pr_creator on any iteration where the required test layers have not all passed

### Requirement: Runtime Code Quality Gate Before Review Approval

The runtime MUST enforce automated code-quality checks on customer code produced by agents before reviewer approval is allowed, including linting, type or static analysis for the target stack, and SOLID-aligned design checks declared in the task list.

#### Scenario: Lint and static analysis are part of the gate
- **WHEN** the tester completes unit and end-to-end execution
- **THEN** the same stage runs the configured linters and static or type analysis for the target repository
- **AND** reviewer approval is blocked while those checks are failing

#### Scenario: SOLID-aligned design checks are explicit
- **WHEN** the planner records design checks tied to single-responsibility, open-closed, Liskov substitution, interface segregation, or dependency-inversion concerns for the ticket
- **THEN** the reviewer validates that the implementation does not violate the declared design checks
- **AND** detected violations route back to coder or planner within retry limits before PR creation can proceed

