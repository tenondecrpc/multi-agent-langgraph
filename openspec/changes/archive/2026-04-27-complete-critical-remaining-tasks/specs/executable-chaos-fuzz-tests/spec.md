## ADDED Requirements

### Requirement: Chaos test for worker kill
The test suite SHALL include a chaos scenario that simulates a worker process being killed mid-execution.

#### Scenario: Worker kill simulation
- **WHEN** the chaos test runs
- **THEN** it verifies the system can detect and recover from a worker crash

### Requirement: Chaos test for Redis partition
The test suite SHALL include a chaos scenario that simulates Redis becoming unavailable.

#### Scenario: Redis partition simulation
- **WHEN** the chaos test runs
- **THEN** it verifies the system handles Redis unavailability gracefully

### Requirement: Chaos test for database loss
The test suite SHALL include a chaos scenario that simulates a brief database connection loss.

#### Scenario: Database loss simulation
- **WHEN** the chaos test runs
- **THEN** it verifies the system reconnects after database recovery

### Requirement: API fuzz tests with schemathesis
The test suite SHALL use schemathesis to fuzz-test API endpoints with malformed payloads.

#### Scenario: Webhook rejects malformed payload under fuzz
- **WHEN** schemathesis sends malformed JSON to the webhook endpoint
- **THEN** the endpoint returns a `4xx` error

### Requirement: Config fuzz tests with hypothesis
The test suite SHALL use hypothesis to fuzz-test routing and budget configuration.

#### Scenario: Routing selects valid provider under fuzz
- **WHEN** hypothesis generates random routing configurations
- **THEN** the routing always selects a valid provider or fails closed

### Requirement: Prompt regression with golden outputs
The test suite SHALL include prompt regression tests that compare outputs against golden fixtures.

#### Scenario: Planner output matches golden fixture
- **WHEN** the planner processes a known fixture
- **THEN** the output matches the golden reference within tolerance
