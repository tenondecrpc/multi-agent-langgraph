## ADDED Requirements

### Requirement: Rollouts And Flags Are Defined As Code

Argo Rollout resources, AnalysisTemplates, and flag catalog SHALL live in the repository under `helm/` and `backend/` and SHALL be promoted via the same progressive-delivery pipeline they govern.

#### Scenario: Rollout change uses the canary path
- **WHEN** a PR modifies the Rollout or AnalysisTemplate
- **THEN** the change is applied through a canary rollout itself
- **AND** not via a direct apply that skips analysis
