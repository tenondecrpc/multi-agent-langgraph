"""Shared pytest fixtures for the backend test suite."""

# Configure required environment variables BEFORE any backend imports.
# This must be at the very top of the file, before any other imports.
import os

os.environ.setdefault("BACKEND_ENCRYPTION_ACTIVE_KEY_ID", "test-key-001")
os.environ.setdefault(
    "BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY",
    "JMJFil3dNxg-vhMCYVebCtquYMmsmeIYu9qkZsWVlrU=",
)
os.environ.setdefault("BACKEND_WEBHOOK_SHARED_SECRET", "test-webhook-secret-for-testing")

from unittest.mock import MagicMock

import pytest

from backend.persistence.testing.runtime import InMemoryRunRepository


@pytest.fixture
def run_repository() -> InMemoryRunRepository:
    """Provide an in-memory run repository for unit tests."""
    return InMemoryRunRepository()


@pytest.fixture
def mock_redis() -> MagicMock:
    """Provide a mock Redis client."""
    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.set = MagicMock(return_value=True)
    redis.delete = MagicMock(return_value=1)
    redis.exists = MagicMock(return_value=False)
    return redis


@pytest.fixture
def mock_arq_worker(mock_redis) -> MagicMock:
    """Provide a mock ARQ worker context."""
    worker = MagicMock()
    worker.redis = mock_redis
    return worker


@pytest.fixture
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"


@pytest.fixture
def synthetic_jira_webhook() -> dict:
    """Provide a synthetic Jira webhook payload for testing."""
    return {
        "webhookEvent": "jira:issue_created",
        "issue": {
            "id": "10001",
            "key": "PROJ-1",
            "fields": {
                "summary": "Test ticket for synthetic evaluation",
                "description": "This is a synthetic ticket for testing purposes.",
                "issuetype": {"name": "Story"},
                "project": {"key": "PROJ"},
            },
        },
    }


@pytest.fixture
def synthetic_graph_config() -> dict:
    """Provide a synthetic graph configuration for testing."""
    return {
        "tenant_id": "tenant-test-001",
        "team_id": "team-alpha",
        "provider_priority": ["openai", "anthropic", "local"],
        "budget_cap_usd": 10.0,
        "max_autonomous_iterations": 5,
        "require_human_approval": False,
        "sandbox_timeout_seconds": 300,
    }
