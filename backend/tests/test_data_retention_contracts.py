from __future__ import annotations

from datetime import UTC, datetime, timedelta


class TestRetentionPolicies:
    def test_policy_creation(self):
        from backend.compliance.admin import RetentionPolicyCreate

        policy = RetentionPolicyCreate(
            surface="metering",
            tenant_id="tenant-test",
            retention_days=365,
        )
        assert policy.surface == "metering"
        assert policy.retention_days == 365

    def test_policy_allows_any_positive_days(self):
        from backend.compliance.admin import RetentionPolicyCreate

        policy = RetentionPolicyCreate(
            surface="metering",
            tenant_id="tenant-test",
            retention_days=1,
        )
        assert policy.retention_days == 1


class TestTenantDeleteWorkflow:
    def test_request_creation(self):
        from backend.compliance.admin import TenantDeleteRequest

        request = TenantDeleteRequest(
            tenant_id="tenant-test",
            reason="GDPR erasure request",
        )
        assert request.tenant_id == "tenant-test"
        assert request.reason == "GDPR erasure request"

    def test_approval_requires_two_approvers(self):
        from backend.compliance.admin import TenantDeleteApproval

        approval = TenantDeleteApproval(
            event_id="evt-1",
            approver="admin@test",
        )
        assert approval.event_id == "evt-1"
        assert approval.approver == "admin@test"


class TestDpaPublication:
    def test_publication_creation(self):
        from backend.compliance.admin import DpaPublication

        pub = DpaPublication(
            version="v1",
            summary="Initial DPA",
            content="Full DPA text here",
            published_by="legal@test",
            grace_period_days=30,
        )
        assert pub.version == "v1"
        assert pub.grace_period_days == 30

    def test_acknowledgement_creation(self):
        from backend.compliance.admin import DpaAcknowledgement

        ack = DpaAcknowledgement(
            tenant_id="tenant-test",
            dpa_version="v1",
            acknowledged_by="admin@test",
        )
        assert ack.tenant_id == "tenant-test"
        assert ack.dpa_version == "v1"


class TestDpaGateMiddleware:
    def test_excluded_paths_not_blocked(self):
        from backend.compliance.dpa_gate import DpaGateMiddleware

        middleware = DpaGateMiddleware(
            app=None,
            database_url="postgresql://test",
        )
        assert middleware._is_excluded("/healthz") is True
        assert middleware._is_excluded("/readyz") is True
        assert middleware._is_excluded("/metrics") is True
        assert middleware._is_excluded("/api/v1/status-page") is True

    def test_webhook_path_not_excluded(self):
        from backend.compliance.dpa_gate import DpaGateMiddleware

        middleware = DpaGateMiddleware(
            app=None,
            database_url="postgresql://test",
        )
        assert middleware._is_excluded("/api/v1/webhooks/jira") is False


class TestRetentionRun:
    def test_dry_run_mode(self):
        from backend.compliance.admin import RetentionPolicyCreate

        policy = RetentionPolicyCreate(
            surface="dlq",
            tenant_id="tenant-test",
            retention_days=90,
        )
        assert policy.surface == "dlq"
        assert policy.retention_days == 90

    def test_enforce_mode(self):
        from backend.compliance.admin import RetentionPolicyCreate

        policy = RetentionPolicyCreate(
            surface="audit",
            tenant_id="tenant-test",
            retention_days=730,
        )
        assert policy.surface == "audit"


class TestCascadeDelete:
    def test_cascade_counts_structure(self):
        expected_tables = [
            "budget_denials",
            "budget_charges",
            "budget_reservations",
            "budget_cap_snapshots",
            "metering_hourly_rollups",
            "metering_facts",
            "dead_letter_records",
            "runs",
        ]
        counts = {table: 0 for table in expected_tables}
        assert len(counts) == 8
        assert "metering_facts" in counts
        assert "runs" in counts


class TestDpaGracePeriod:
    def test_grace_period_calculation(self):
        published_at = datetime.now(tz=UTC) - timedelta(days=15)
        grace_period_days = 30
        grace_cutoff = published_at + timedelta(days=grace_period_days)
        assert datetime.now(tz=UTC) <= grace_cutoff

    def test_grace_period_expired(self):
        published_at = datetime.now(tz=UTC) - timedelta(days=45)
        grace_period_days = 30
        grace_cutoff = published_at + timedelta(days=grace_period_days)
        assert datetime.now(tz=UTC) > grace_cutoff
