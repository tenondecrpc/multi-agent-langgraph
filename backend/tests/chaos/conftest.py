"""Shared fixtures for chaos testing."""

import os
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def chaos_scenario_name(request) -> str:
    """Provide the current chaos scenario name from the test marker."""
    marker = request.node.get_closest_marker("chaos_scenario")
    if marker:
        return marker.args[0]
    return "unknown"


@pytest.fixture
def mock_llm_provider_garbage() -> MagicMock:
    """Simulate an LLM provider returning garbage output."""
    provider = MagicMock()
    provider.invoke.return_value = {
        "content": "!!!GARBAGE!!! {{{invalid json}}}",
        "usage": {"total_tokens": 0},
    }
    return provider


@pytest.fixture
def mock_all_providers_down() -> MagicMock:
    """Simulate all LLM providers being unavailable."""
    provider = MagicMock()
    provider.invoke.side_effect = ConnectionError("All providers unreachable")
    return provider


@pytest.fixture
def mock_vault_unavailable() -> MagicMock:
    """Simulate HashiCorp Vault being unavailable."""
    vault = MagicMock()
    vault.read_secret.side_effect = ConnectionError("Vault connection refused")
    return vault


@pytest.fixture
def mock_budget_race_condition() -> dict:
    """Provide a budget state that triggers a race condition."""
    return {
        "tenant_id": "tenant-race-001",
        "budget_cap_usd": 5.0,
        "spent_usd": 4.99,
        "concurrent_requests": 3,
        "cost_per_request_usd": 0.01,
    }


@pytest.fixture
def ephemeral_cluster_config() -> dict:
    """Provide configuration for ephemeral cluster testing (kind/k3d)."""
    return {
        "cluster_type": os.getenv("CHAOS_CLUSTER_TYPE", "kind"),
        "cluster_name": os.getenv("CHAOS_CLUSTER_NAME", "chaos-test"),
        "namespace": os.getenv("CHAOS_NAMESPACE", "chaos-test"),
        "helm_chart_path": os.getenv("HELM_CHART_PATH", "../../helm"),
    }
