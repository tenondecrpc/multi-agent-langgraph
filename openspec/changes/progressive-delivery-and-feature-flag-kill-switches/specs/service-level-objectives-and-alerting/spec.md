## ADDED Requirements

### Requirement: SLO Queries Feed Rollout Analysis

Existing SLO and burn-rate Prometheus queries SHALL be reusable as `AnalysisTemplate` inputs so progressive delivery automatically inherits the error-budget policy.

#### Scenario: Burn-rate alert and canary analysis agree
- **WHEN** a burn-rate threshold is crossed
- **THEN** the corresponding AnalysisTemplate evaluates the same condition
- **AND** both the operator alert and the rollback happen coherently
