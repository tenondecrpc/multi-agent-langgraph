## ADDED Requirements

### Requirement: Chaos test for worker kill
The test suite SHALL include a chaos scenario that simulates a worker process being killed mid-execution and verifies that the run can be resumed from its last checkpoint.

#### Scenario: Worker kill and resume
- **WHEN** a worker is processing a run and is killed
- **AND** a new worker picks up the same run
- **THEN** the run resumes from the last checkpoint without data loss

### Requirement: Chaos test for Redis partition
The test suite SHALL include a chaos scenario that simulates Redis becoming unavailable and verifies that the system falls back to PostgreSQL-only operation for critical paths.

#### Scenario: Redis partition fallback
- **WHEN** Redis becomes unreachable during budget reservation
- **THEN** the system either queues the reservation for retry or falls back to PostgreSQL-only budget checking

### Requirement: Chaos test for database loss
The test suite SHALL include a chaos scenario that simulates a brief database connection loss and verifies that the system recovers and reconnects.

#### Scenario: Database connection loss and recovery
- **WHEN** the database becomes unreachable for a short period
- **AND** the database recovers
- **THEN** the system reconnects and processes pending requests

### Requirement: API fuzz tests with schemathesis
The test suite SHALL use schemathesis to fuzz-test all API endpoints with malformed payloads, boundary values, and invalid schemas.

#### Scenario: Webhook rejects malformed payload under fuzz
- **WHEN** schemathesis sends malformed JSON to the webhook endpoint
- **THEN** the endpoint returns a `4xx` error and does not crash

#### Scenario: Admin API requires authentication under fuzz
- **WHEN** schemathesis sends requests to admin endpoints without auth headers
- **THEN** all requests return `401 Unauthorized`

### Requirement: Prompt regression with golden outputs
The test suite SHALL include prompt regression tests that compare planner and reviewer outputs against golden reference fixtures.

#### Scenario: Planner output matches golden fixture
- **WHEN** the planner processes a known Jira ticket fixture
- **THEN** the generated feature spec matches the golden reference within a tolerance threshold

#### Scenario: Reviewer output matches golden fixture
- **WHEN** the reviewer processes a known code review fixture
- **THEN** the review decision matches the golden reference
