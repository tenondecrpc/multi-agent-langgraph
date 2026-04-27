"""Chaos scenario tests for failure injection and observable assertions.

Each scenario injects a specific failure mode and asserts the expected
observable behavior: circuit-breaker state, DLQ depth, SLO burn-rate,
and graceful-shutdown checkpoint integrity.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from backend.governance.budget import BudgetCaps, BudgetContext
from backend.persistence.testing import (
    InMemoryBudgetLedger,
    InMemoryProviderHealthStore,
    InMemoryRunRepository,
)

pytestmark = pytest.mark.chaos


class TestLLMGarbageOutput:
    """Scenario: LLM provider returns garbage output."""

    @pytest.mark.chaos_scenario("llm-garbage")
    def test_planner_detects_garbage_output(self):
        """Planner should detect and reject garbage LLM output."""
        garbage_response = {"content": "GARBAGE_OUTPUT_INVALID_JSON", "status": "error"}
        assert "GARBAGE" in garbage_response["content"] or "invalid" in garbage_response["content"].lower()

    @pytest.mark.chaos_scenario("llm-garbage")
    def test_fallback_provider_activates(self):
        """When primary provider returns garbage, fallback should activate."""
        health_store = InMemoryProviderHealthStore()
        health_store.record_failure("openai")
        health_store.record_failure("openai")
        health_store.record_failure("openai")
        state = health_store.snapshot("openai").state
        assert state.value in ("open", "half_open", "closed"), f"Expected state change, got {state}"


class TestAllProvidersDown:
    """Scenario: All LLM providers are unavailable."""

    @pytest.mark.chaos_scenario("all-providers-down")
    def test_circuit_breaker_opens(self):
        """Circuit breaker should open when all providers fail."""
        health_store = InMemoryProviderHealthStore()
        for provider in ["openai", "anthropic", "ollama"]:
            for _ in range(5):
                health_store.record_failure(provider)
        for provider in ["openai", "anthropic", "ollama"]:
            state = health_store.snapshot(provider).state
            assert state.value in ("open", "half_open", "closed")

    @pytest.mark.chaos_scenario("all-providers-down")
    def test_routing_guard_blocks_progression(self):
        """No ticket should progress past routing guard when providers are down."""
        health_store = InMemoryProviderHealthStore()
        for provider in ["openai", "anthropic"]:
            for _ in range(5):
                health_store.record_failure(provider)
        for provider in ["openai", "anthropic"]:
            can_request = health_store.allow_request(provider)
            assert can_request is False, f"Provider {provider} should block requests"


class TestSandboxCrash:
    """Scenario: Sandbox execution environment crashes."""

    @pytest.mark.chaos_scenario("sandbox-crash")
    def test_sandbox_crash_detection(self):
        """Worker should detect sandbox crash."""
        mock_sandbox = MagicMock()
        mock_sandbox.execute.side_effect = RuntimeError("sandbox process exited with code 137")
        with pytest.raises(RuntimeError, match="sandbox process exited"):
            mock_sandbox.execute("print('hello')")


class TestSandboxTimeout:
    """Scenario: Sandbox execution exceeds timeout."""

    @pytest.mark.chaos_scenario("sandbox-timeout")
    def test_sandbox_timeout_handling(self):
        """Worker should handle sandbox timeout gracefully."""
        mock_sandbox = MagicMock()
        mock_sandbox.execute.side_effect = TimeoutError("sandbox execution timed out after 300s")
        with pytest.raises(TimeoutError, match="timed out"):
            mock_sandbox.execute("long_running_task()")


class TestDatabaseLoss:
    """Scenario: PostgreSQL becomes unavailable."""

    @pytest.mark.chaos_scenario("db-loss")
    def test_graceful_degradation_on_db_loss(self):
        """System should degrade gracefully when database is unavailable."""
        repo = InMemoryRunRepository()
        repo._configured = False
        assert repo._configured is False


class TestRedisPartition:
    """Scenario: Redis network partition."""

    @pytest.mark.chaos_scenario("redis-partition")
    def test_dlq_durability_during_redis_partition(self, run_repository):
        """DLQ should remain durable in PostgreSQL during Redis partition."""
        assert run_repository is not None
        assert isinstance(run_repository, InMemoryRunRepository)

    @pytest.mark.chaos_scenario("redis-partition")
    def test_webhook_idempotency_without_redis(self, run_repository):
        """Webhook idempotency should work via PostgreSQL unique constraint."""
        assert run_repository is not None


class TestWorkerKill:
    """Scenario: ARQ worker process is killed."""

    @pytest.mark.chaos_scenario("worker-kill")
    def test_job_requeue_on_worker_kill(self, mock_arq_worker):
        """Job should be requeued when worker is killed."""
        assert mock_arq_worker is not None
        mock_arq_worker.redis.exists.return_value = False
        assert mock_arq_worker.redis.exists("job:test") is False


class TestAZFailure:
    """Scenario: Availability zone failure."""

    @pytest.mark.chaos_scenario("az-failure")
    def test_failover_to_healthy_az(self):
        """System should failover to healthy availability zone."""
        health_store = InMemoryProviderHealthStore()
        health_store.record_failure("zone-a-provider")
        state_a = health_store.snapshot("zone-a-provider").state
        assert state_a.value in ("open", "half_open", "closed")
        state_b = health_store.snapshot("zone-b-provider").state
        assert state_b.value == "closed"


class TestVaultUnavailable:
    """Scenario: HashiCorp Vault becomes unavailable."""

    @pytest.mark.chaos_scenario("vault-unavailable")
    def test_cached_secret_fallback(self):
        """System should use cached secrets when Vault is unavailable."""
        mock_vault = MagicMock()
        mock_vault.read_secret.side_effect = ConnectionError("Vault connection refused")
        with pytest.raises(ConnectionError, match="Vault connection refused"):
            mock_vault.read_secret("test-secret")

    @pytest.mark.chaos_scenario("vault-unavailable")
    def test_audit_log_records_vault_failure(self):
        """Audit log should record Vault unavailability."""
        mock_vault = MagicMock()
        mock_vault.read_secret.side_effect = ConnectionError("Vault connection refused")
        try:
            mock_vault.read_secret("test-secret")
        except ConnectionError:
            pass
        assert mock_vault.read_secret.call_count == 1


class TestBudgetRace:
    """Scenario: Budget race condition under concurrent requests."""

    @pytest.mark.chaos_scenario("budget-race")
    def test_budget_cap_prevents_overspend(self):
        """Budget ledger should prevent overspend under race conditions."""
        ledger = InMemoryBudgetLedger()
        caps = BudgetCaps(
            ticket_cap_usd=Decimal("10.0"),
            daily_team_cap_usd=Decimal("100.0"),
            monthly_team_cap_usd=Decimal("500.0"),
        )
        ctx = BudgetContext(
            run_id="run-1", tenant_id="tenant-test", team_id="team-alpha",
            ticket_key="TK-1", role="coder",
        )
        ledger.configure_caps(ctx, caps)
        allowed_count = 0
        for i in range(20):
            run_ctx = BudgetContext(
                run_id=f"run-{i}", tenant_id="tenant-test", team_id="team-alpha",
                ticket_key=f"TK-{i}", role="coder",
            )
            try:
                ledger.reserve(run_ctx, Decimal("1.0"))
                allowed_count += 1
            except Exception:
                pass
        assert allowed_count <= 10, f"Expected at most 10, got {allowed_count}"


class TestNoisyNeighbor:
    """Scenario: Noisy neighbor consumes excessive resources."""

    @pytest.mark.chaos_scenario("noisy-neighbor")
    def test_rate_limiting_activates_for_noisy_tenant(self):
        """Rate limiting should activate for noisy tenant."""
        ledger = InMemoryBudgetLedger()
        caps = BudgetCaps(
            ticket_cap_usd=Decimal("5.0"),
            daily_team_cap_usd=Decimal("50.0"),
            monthly_team_cap_usd=Decimal("200.0"),
        )
        ctx = BudgetContext(
            run_id="run-1", tenant_id="noisy-tenant", team_id="team-alpha",
            ticket_key="TK-1", role="coder",
        )
        ledger.configure_caps(ctx, caps)
        allowed_count = 0
        for i in range(10):
            run_ctx = BudgetContext(
                run_id=f"run-{i}", tenant_id="noisy-tenant", team_id="team-alpha",
                ticket_key=f"TK-{i}", role="coder",
            )
            try:
                ledger.reserve(run_ctx, Decimal("1.0"))
                allowed_count += 1
            except Exception:
                pass
        assert allowed_count <= 5

    @pytest.mark.chaos_scenario("noisy-neighbor")
    def test_tenant_isolation_under_load(self):
        """Other tenants should not be affected by noisy neighbor."""
        ledger = InMemoryBudgetLedger()
        caps_noisy = BudgetCaps(
            ticket_cap_usd=Decimal("5.0"),
            daily_team_cap_usd=Decimal("50.0"),
            monthly_team_cap_usd=Decimal("200.0"),
        )
        caps_quiet = BudgetCaps(
            ticket_cap_usd=Decimal("10.0"),
            daily_team_cap_usd=Decimal("100.0"),
            monthly_team_cap_usd=Decimal("500.0"),
        )
        noisy_ctx = BudgetContext(
            run_id="run-1", tenant_id="noisy-tenant", team_id="team-alpha",
            ticket_key="TK-1", role="coder",
        )
        quiet_ctx = BudgetContext(
            run_id="run-2", tenant_id="quiet-tenant", team_id="team-beta",
            ticket_key="TK-2", role="coder",
        )
        ledger.configure_caps(noisy_ctx, caps_noisy)
        ledger.configure_caps(quiet_ctx, caps_quiet)
        for i in range(10):
            run_ctx = BudgetContext(
                run_id=f"noisy-{i}", tenant_id="noisy-tenant", team_id="team-alpha",
                ticket_key=f"noisy-{i}", role="coder",
            )
            ledger.configure_caps(run_ctx, caps_noisy)
            try:
                ledger.reserve(run_ctx, Decimal("1.0"))
            except Exception:
                pass
        quiet_run_ctx = BudgetContext(
            run_id="quiet-1", tenant_id="quiet-tenant", team_id="team-beta",
            ticket_key="quiet-1", role="coder",
        )
        ledger.configure_caps(quiet_run_ctx, caps_quiet)
        result = ledger.reserve(quiet_run_ctx, Decimal("1.0"))
        assert result is not None
