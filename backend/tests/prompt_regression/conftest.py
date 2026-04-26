"""Shared fixtures for prompt regression testing."""

import pytest


@pytest.fixture
def planner_fixtures() -> list[dict]:
    """Versioned fixtures for planner evaluation.

    Each fixture contains:
    - input: The Jira ticket context and planning request
    - expected_output: Golden output or schema for validation
    - metadata: Fixture version, creation date, and retirement status
    """
    return [
        {
            "id": "planner-001",
            "version": "1.0",
            "input": {
                "summary": "Implement user authentication endpoint",
                "description": "Add JWT-based authentication to the API.",
                "type": "Story",
            },
            "expected_schema": {
                "has_task_list": True,
                "has_implementation_plan": True,
                "identifies_dependencies": True,
            },
            "metadata": {
                "created": "2026-04-26",
                "retired": False,
                "category": "authentication",
            },
        },
        {
            "id": "planner-002",
            "version": "1.0",
            "input": {
                "summary": "Fix database connection pool exhaustion",
                "description": "The connection pool is exhausted under load.",
                "type": "Bug",
            },
            "expected_schema": {
                "has_task_list": True,
                "has_implementation_plan": True,
                "identifies_root_cause": True,
            },
            "metadata": {
                "created": "2026-04-26",
                "retired": False,
                "category": "database",
            },
        },
    ]


@pytest.fixture
def reviewer_fixtures() -> list[dict]:
    """Versioned fixtures for reviewer evaluation.

    Each fixture contains:
    - input: The code diff and implementation context
    - expected_output: Golden review output or schema for validation
    - metadata: Fixture version, creation date, and retirement status
    """
    return [
        {
            "id": "reviewer-001",
            "version": "1.0",
            "input": {
                "diff": "Added authentication middleware to FastAPI app.",
                "files_changed": ["src/backend/app.py", "src/backend/auth.py"],
                "tests_added": 3,
            },
            "expected_schema": {
                "checks_security": True,
                "checks_tests": True,
                "provides_actionable_feedback": True,
            },
            "metadata": {
                "created": "2026-04-26",
                "retired": False,
                "category": "authentication",
            },
        },
    ]


@pytest.fixture
def regression_tolerance() -> float:
    """Maximum allowed regression tolerance (0.0 to 1.0).

    If the regression score drops below (1.0 - tolerance), CI blocks.
    """
    return 0.1


@pytest.fixture
def langsmith_config() -> dict:
    """Configuration for LangSmith integration."""
    return {
        "api_key_env": "LANGSMITH_API_KEY",
        "project_name": "langgraph-dev-squad-prompt-regression",
        "dataset_name": "planner-reviewer-fixtures",
    }
