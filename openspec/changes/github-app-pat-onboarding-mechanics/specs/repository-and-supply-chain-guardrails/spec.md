## ADDED Requirements

### Requirement: Branch-Protection Verification Is Composed With Existing Guards

The branch-protection verification SHALL run as part of the pre-PR chain together with implementation, tests, diff-size guard, forbidden-path guard, review approval, and pre-PR sync. Order and atomicity of these guards SHALL NOT be bypassable.

#### Scenario: Any missing guard blocks PR creation
- **WHEN** any of the guards (implementation, tests, diff-size, forbidden-path, review approval, pre-PR sync, branch-protection) is not satisfied
- **THEN** the pr_creator node does not open a PR
- **AND** the run escalates via its registered sink
