"""Integration tests for rollout and rollback validation."""

import pytest

from backend.operations.feature_flags import MANDATORY_KILL_SWITCHES, FeatureFlagClient
from backend.operations.release import ReleasePolicy, RolloutAnalysis

pytestmark = pytest.mark.chaos


class TestRolloutRollback:
    """Tests for SLO-driven rollout rollback."""

    def test_healthy_rollout_proceeds(self):
        """Rollout should proceed when all SLOs are healthy."""
        policy = ReleasePolicy(
            stages=[],
            environments=[],
            feature_flags=[],
        )
        analysis = RolloutAnalysis(
            error_budget_burn_rate=0.5,
            health_regressed=False,
            kill_switch_engaged=False,
        )
        decision = policy.evaluate_rollout(analysis)
        assert decision.proceed is True
        assert decision.rollback is False

    def test_health_regression_triggers_rollback(self):
        """Rollout should rollback when health regresses."""
        policy = ReleasePolicy(
            stages=[],
            environments=[],
            feature_flags=[],
        )
        analysis = RolloutAnalysis(
            error_budget_burn_rate=0.5,
            health_regressed=True,
            kill_switch_engaged=False,
        )
        decision = policy.evaluate_rollout(analysis)
        assert decision.rollback is True
        assert "health_regressed" in decision.reasons

    def test_high_burn_rate_triggers_rollback(self):
        """Rollout should rollback when burn rate exceeds threshold."""
        from decimal import Decimal

        policy = ReleasePolicy(
            stages=[],
            environments=[],
            feature_flags=[],
        )
        analysis = RolloutAnalysis(
            error_budget_burn_rate=Decimal("3.0"),
            health_regressed=False,
            kill_switch_engaged=False,
        )
        decision = policy.evaluate_rollout(analysis)
        assert decision.rollback is True
        assert "burn_rate_threshold_exceeded" in decision.reasons

    def test_kill_switch_engaged_triggers_rollback(self):
        """Rollout should rollback when a kill switch is engaged."""
        policy = ReleasePolicy(
            stages=[],
            environments=[],
            feature_flags=[],
        )
        analysis = RolloutAnalysis(
            error_budget_burn_rate=0.5,
            health_regressed=False,
            kill_switch_engaged=True,
        )
        decision = policy.evaluate_rollout(analysis)
        assert decision.rollback is True
        assert "kill_switch_engaged" in decision.reasons


class TestKillSwitchDrill:
    """Tests for quarterly kill-switch drill validation."""

    def test_all_kill_switches_evaluable(self):
        """All mandatory kill switches should be evaluable."""
        client = FeatureFlagClient()
        client.initialize()
        for flag_key in MANDATORY_KILL_SWITCHES:
            state = client.get_kill_switch_state(flag_key)
            assert state.flag_key == flag_key
            assert state.owner is not None

    def test_kill_switch_fail_closed(self):
        """Kill switches should fail closed when provider is unavailable."""
        from backend.operations.feature_flags import FlagProvider

        client = FeatureFlagClient(provider=FlagProvider.POSTGRES_MIRROR)
        client.initialize()
        for flag_key in MANDATORY_KILL_SWITCHES:
            state = client.get_kill_switch_state(flag_key)
            assert state.enabled is False, f"Kill switch {flag_key} should fail closed"


class TestRollbackDrill:
    """Tests for synthetic SLO breach rollback drill."""

    def test_synthetic_slo_breach_triggers_rollback(self):
        """Synthetic SLO breach should trigger automated rollback."""
        from decimal import Decimal

        policy = ReleasePolicy(
            stages=[],
            environments=[],
            feature_flags=[],
        )
        analysis = RolloutAnalysis(
            error_budget_burn_rate=Decimal("5.0"),
            health_regressed=True,
            kill_switch_engaged=True,
        )
        decision = policy.evaluate_rollout(analysis)
        assert decision.rollback is True
        assert len(decision.reasons) == 3
