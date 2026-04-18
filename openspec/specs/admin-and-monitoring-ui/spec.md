# admin-and-monitoring-ui Specification

## Purpose
TBD - created by archiving change phase-6-operator-ui-and-control-room. Update Purpose after archive.
## Requirements
### Requirement: Role-Aware Monitoring And Admin Surface

The frontend MUST provide role-aware monitoring and administration surfaces for viewer, operator, admin, and super-admin users.

#### Scenario: Role scope gates available screens and actions
- **WHEN** a user navigates the product UI
- **THEN** the available dashboard, interrupt, admin, tenant-management, and cost surfaces match the user's authorized role and tenant scope
- **AND** the backend remains the source of truth for authorization

### Requirement: Monitoring Surface Supports Live Operations

The UI MUST provide real-time monitoring for ticket and job execution across the user's allowed scope.

#### Scenario: SSE-backed status updates appear in the dashboard
- **WHEN** active runs change state
- **THEN** authenticated users receive live, tenant-scoped updates through the monitoring surface
- **AND** the UI can represent multiple concurrent tickets without collapsing them into a single-run view

#### Scenario: Break-glass and recovery surfaces are visible to the right roles
- **WHEN** a run pauses on a registered exception path or lands in the DLQ
- **THEN** the appropriate operator-facing surfaces expose the pending interrupt or DLQ record for review, retry, dismissal, or approval according to role

### Requirement: Admin UI Covers Operational Configuration

The admin experience MUST expose the operational surfaces needed to manage agent configuration, dry-run testing, and cost views.

#### Scenario: Admin can manage agent configuration
- **WHEN** an authorized admin opens the administration surfaces
- **THEN** they can inspect and modify agent configurations within the validated role constraints defined by the backend

#### Scenario: Admin can dry-run an agent safely
- **WHEN** an authorized admin triggers the test-agent workflow
- **THEN** the UI surfaces the response and validation result
- **AND** the request stays within the backend guardrails defined for test-agent behavior

