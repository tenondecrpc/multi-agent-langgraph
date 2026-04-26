"""Tests for feature flag service with kill switch enforcement and audit."""

from datetime import UTC, datetime, timedelta

from backend.operations.feature_flag_service import (
    FeatureFlagService,
    FlagToggleRecord,
)


class TestFeatureFlagService:
    """Tests for FeatureFlagService."""

    def test_initialization(self):
        """Service should initialize with default client."""
        service = FeatureFlagService()
        assert service._stale_threshold_days == 90
        assert service._audit_log == []

    def test_initialize_propagates_to_client(self):
        """initialize should propagate to the underlying client."""
        service = FeatureFlagService()
        service.initialize()
        assert service._client._initialized is True

    def test_close_propagates_to_client(self):
        """close should propagate to the underlying client."""
        service = FeatureFlagService()
        service.initialize()
        service.close()
        assert service._client._initialized is False


class TestKillSwitchEnforcement:
    """Tests for kill switch evaluation."""

    def test_single_kill_switch_state(self):
        """is_kill_switch_enabled should return KillSwitchState."""
        service = FeatureFlagService()
        service.initialize()
        state = service.is_kill_switch_enabled("llm_provider_anthropic")
        assert state.flag_key == "llm_provider_anthropic"
        assert state.owner == "llm-governance"

    def test_all_kill_switches_healthy(self):
        """are_all_kill_switches_healthy should return states for all six."""
        service = FeatureFlagService()
        service.initialize()
        states = service.are_all_kill_switches_healthy()
        assert len(states) == 6
        for flag_key in [
            "llm_provider_anthropic",
            "llm_provider_openai",
            "pr_creation",
            "graph_activation",
            "sandbox_runtime_gvisor",
            "ticket_processing",
        ]:
            assert flag_key in states

    def test_get_mandatory_kill_switches(self):
        """get_mandatory_kill_switches should return the catalog."""
        service = FeatureFlagService()
        catalog = service.get_mandatory_kill_switches()
        assert len(catalog) == 6


class TestFlagAudit:
    """Tests for flag toggle audit logging."""

    def test_toggle_flag_records_audit(self):
        """toggle_flag should record an audit entry."""
        service = FeatureFlagService()
        service.initialize()
        record = service.toggle_flag(
            flag_key="llm_provider_anthropic",
            enabled=False,
            changed_by="admin-user",
            reason="Provider outage",
        )
        assert isinstance(record, FlagToggleRecord)
        assert record.flag_key == "llm_provider_anthropic"
        assert record.new_enabled is False
        assert record.changed_by == "admin-user"
        assert record.reason == "Provider outage"

    def test_audit_log_grows_with_toggles(self):
        """Audit log should accumulate toggle records."""
        service = FeatureFlagService()
        service.initialize()
        service.toggle_flag("llm_provider_anthropic", False, "user1")
        service.toggle_flag("pr_creation", False, "user2")
        assert len(service.get_audit_log()) == 2

    def test_audit_log_filter_by_flag_key(self):
        """get_audit_log should filter by flag key."""
        service = FeatureFlagService()
        service.initialize()
        service.toggle_flag("llm_provider_anthropic", False, "user1")
        service.toggle_flag("pr_creation", False, "user2")
        filtered = service.get_audit_log(flag_key="llm_provider_anthropic")
        assert len(filtered) == 1
        assert filtered[0].flag_key == "llm_provider_anthropic"


class TestStaleFlagDetection:
    """Tests for stale flag detection."""

    def test_detects_stale_flags(self):
        """detect_stale_flags should identify flags past threshold."""
        service = FeatureFlagService(stale_threshold_days=90)
        now = datetime.now(UTC)
        flags = [
            {
                "flag_key": "old-flag",
                "owner": "team-a",
                "last_modified_at": now - timedelta(days=100),
            },
            {
                "flag_key": "recent-flag",
                "owner": "team-b",
                "last_modified_at": now - timedelta(days=10),
            },
        ]
        alerts = service.detect_stale_flags(flags)
        assert len(alerts) == 1
        assert alerts[0].flag_key == "old-flag"
        assert alerts[0].days_since_modified == 100

    def test_no_alerts_for_fresh_flags(self):
        """No alerts should be generated for fresh flags."""
        service = FeatureFlagService(stale_threshold_days=90)
        now = datetime.now(UTC)
        flags = [
            {
                "flag_key": "fresh-flag",
                "owner": "team-a",
                "last_modified_at": now - timedelta(days=30),
            },
        ]
        alerts = service.detect_stale_flags(flags)
        assert len(alerts) == 0

    def test_alert_includes_threshold(self):
        """StaleFlagAlert should include the threshold value."""
        service = FeatureFlagService(stale_threshold_days=60)
        now = datetime.now(UTC)
        flags = [
            {
                "flag_key": "stale-flag",
                "owner": "team-a",
                "last_modified_at": now - timedelta(days=90),
            },
        ]
        alerts = service.detect_stale_flags(flags)
        assert len(alerts) == 1
        assert alerts[0].stale_threshold_days == 60
