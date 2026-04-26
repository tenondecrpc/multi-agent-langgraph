"""Shared fixtures for fuzz testing."""

import pytest


@pytest.fixture
def openapi_spec_path() -> str:
    """Path to the OpenAPI specification for schemathesis."""
    return "/openapi.json"


@pytest.fixture
def base_url() -> str:
    """Base URL for the API under test."""
    return "http://localhost:8000"


@pytest.fixture
def graph_config_invariants() -> list[str]:
    """List of GraphConfig invariants that fuzz tests must preserve."""
    return [
        "tenant_id is non-empty",
        "budget_cap_usd is positive",
        "max_autonomous_iterations is positive",
        "provider_priority is non-empty list",
        "sandbox_timeout_seconds is positive",
    ]
