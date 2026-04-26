# progressive-delivery-and-kill-switches Specification

## Purpose
Defines the progressive delivery and feature-flag kill-switch capabilities for the LangGraph Dev Squad. Ensures SLO-driven canary rollouts with automated rollback, blue/green frontend deployment, and six mandatory kill switches with audit and fail-safe behavior.

## Requirements

### Requirement: Canary Rollout With SLO-Driven Analysis

API and worker deployments SHALL use Argo Rollouts with canary steps 5, 25, 50, 100 percent. Each pause SHALL run an SLO-driven `AnalysisTemplate` against error rate, latency p95, circuit-breaker events, DLQ growth, and pool saturation. Any failing metric SHALL trigger automated rollback.

#### Scenario: SLO breach rolls back canary
- **WHEN** analysis reports a failing metric during the canary pause
- **THEN** Argo Rollouts rolls back to the previous stable revision
- **AND** an incident is created with the analysis artifact attached

### Requirement: Blue/Green For Frontend

Frontend releases SHALL use blue/green with an explicit promote step.

#### Scenario: Failed smoke blocks promote
- **WHEN** post-deploy smoke fails on the inactive color
- **THEN** promote is blocked
- **AND** the active color stays on the previous release

### Requirement: Six Mandatory Kill Switches

The backend SHALL expose kill switches for `llm_provider_anthropic`, `llm_provider_openai`, `pr_creation`, `graph_activation`, `sandbox_runtime_gvisor`, and `ticket_processing`. Toggling any SHALL emit an audit event.

#### Scenario: Disabling PR creation halts repo writes
- **WHEN** `pr_creation` is toggled off
- **THEN** the pr_creator node fails closed
- **AND** any in-flight run pauses with a documented escalation reason

### Requirement: Flag-Service Fail-Safe With PostgreSQL Mirror

The backend SHALL mirror flag state to a PostgreSQL `feature_flag_state` table. If the flag service is unreachable, the backend SHALL fall back to the last-known state with a documented TTL.

#### Scenario: Flag service outage uses mirrored state
- **WHEN** Unleash is unreachable within the TTL
- **THEN** the backend uses the mirrored state
- **AND** an alert fires for the outage

### Requirement: Stale-Flag Discipline

Any feature flag older than 90 days without change SHALL raise a warning alert to its owning team. A flag registry SHALL list owner, created_at, last_change_at, intended_retirement_at.

#### Scenario: Stale flag triggers cleanup alert
- **WHEN** a flag passes 90 days without toggle
- **THEN** a warning alert is emitted with owner and age
- **AND** PR templates include a flag-cleanup reminder
