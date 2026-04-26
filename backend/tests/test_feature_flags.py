"""Tests for feature flag client and kill switch evaluation."""

import pytest

from backend.operations.feature_flags import (
    MANDATORY_KILL_SWITCHES,
    FeatureFlagClient,
    FlagProvider,
    KillSwitchState,
)


class TestFeatureFlagClient:
    """Tests for FeatureFlagClient."""

    def test_initialization(self):
        """Client should initialize with default provider."""
        client = FeatureFlagClient()
        assert client._provider == FlagProvider.UNLEASH
        assert client._app_name == "langgraph-dev-squad"
        assert client._initialized is False

    def test_initialize_sets_flag(self):
        """Initialize should set the initialized flag."""
        client = FeatureFlagClient()
        client.initialize()
        assert client._initialized is True

    def test_close_resets_flag(self):
        """Close should reset the initialized flag."""
        client = FeatureFlagClient()
        client.initialize()
        client.close()
        assert client._initialized is False

    def test_is_enabled_initializes_automatically(self):
        """is_enabled should auto-initialize if not initialized."""
        client = FeatureFlagClient()
        result = client.is_enabled("test-flag")
        assert client._initialized is True
        assert isinstance(result, bool)

    def test_unsupported_provider_raises(self):
        """Unsupported primary provider should raise ValueError."""
        client = FeatureFlagClient(provider=FlagProvider.POSTGRES_MIRROR)
        client.initialize()
        with pytest.raises(ValueError, match="Unsupported primary provider"):
            client._evaluate_primary("test-flag", {})


class TestKillSwitches:
    """Tests for mandatory kill switches."""

    def test_six_mandatory_kill_switches_exist(self):
        """There should be exactly six mandatory kill switches."""
        assert len(MANDATORY_KILL_SWITCHES) == 6

    def test_all_kill_switches_have_required_fields(self):
        """Each kill switch should have owner and description."""
        required_fields = {"owner", "description"}
        for flag_key, meta in MANDATORY_KILL_SWITCHES.items():
            assert required_fields.issubset(meta.keys()), f"Missing fields in {flag_key}"

    def test_expected_kill_switch_keys(self):
        """The expected kill switch keys should be present."""
        expected_keys = {
            "llm_provider_anthropic",
            "llm_provider_openai",
            "pr_creation",
            "graph_activation",
            "sandbox_runtime_gvisor",
            "ticket_processing",
        }
        assert set(MANDATORY_KILL_SWITCHES.keys()) == expected_keys

    def test_get_kill_switch_state_returns_state(self):
        """get_kill_switch_state should return a KillSwitchState."""
        client = FeatureFlagClient()
        client.initialize()
        state = client.get_kill_switch_state("llm_provider_anthropic")
        assert isinstance(state, KillSwitchState)
        assert state.flag_key == "llm_provider_anthropic"
        assert state.owner == "llm-governance"

    def test_unknown_kill_switch_raises(self):
        """Unknown kill switch should raise ValueError."""
        client = FeatureFlagClient()
        client.initialize()
        with pytest.raises(ValueError, match="Unknown kill switch"):
            client.get_kill_switch_state("nonexistent-flag")

    def test_kill_switch_fail_closed_on_error(self):
        """Kill switch should fail closed (disabled) on evaluation error."""
        client = FeatureFlagClient(provider=FlagProvider.POSTGRES_MIRROR)
        client.initialize()
        state = client.get_kill_switch_state("llm_provider_anthropic")
        assert state.enabled is False
