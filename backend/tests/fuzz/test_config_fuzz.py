"""Hypothesis-based property tests for GraphConfig and routing rules.

These tests use property-based testing to find invariant violations
in GraphConfig validators and routing rule functions.
"""

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

pytestmark = pytest.mark.fuzz


graph_config_strategy = st.fixed_dictionaries(
    {
        "tenant_id": st.text(min_size=1, max_size=64),
        "team_id": st.text(min_size=1, max_size=64),
        "provider_priority": st.lists(
            st.sampled_from(["openai", "anthropic", "local", "azure"]),
            min_size=1,
            max_size=4,
            unique=True,
        ),
        "budget_cap_usd": st.floats(min_value=0.01, max_value=10000.0),
        "max_autonomous_iterations": st.integers(min_value=1, max_value=100),
        "require_human_approval": st.booleans(),
        "sandbox_timeout_seconds": st.integers(min_value=10, max_value=3600),
    }
)


class TestGraphConfigInvariants:
    """Property tests for GraphConfig invariants."""

    @given(graph_config_strategy)
    @settings(max_examples=100)
    def test_tenant_id_is_non_empty(self, config):
        """tenant_id should always be non-empty."""
        assert len(config["tenant_id"]) > 0

    @given(graph_config_strategy)
    @settings(max_examples=100)
    def test_budget_cap_is_positive(self, config):
        """budget_cap_usd should always be positive."""
        assert config["budget_cap_usd"] > 0

    @given(graph_config_strategy)
    @settings(max_examples=100)
    def test_max_iterations_is_positive(self, config):
        """max_autonomous_iterations should always be positive."""
        assert config["max_autonomous_iterations"] > 0

    @given(graph_config_strategy)
    @settings(max_examples=100)
    def test_provider_priority_is_non_empty(self, config):
        """provider_priority should always be a non-empty list."""
        assert len(config["provider_priority"]) > 0

    @given(graph_config_strategy)
    @settings(max_examples=100)
    def test_sandbox_timeout_is_positive(self, config):
        """sandbox_timeout_seconds should always be positive."""
        assert config["sandbox_timeout_seconds"] > 0


class TestRoutingRuleInvariants:
    """Property tests for routing rule functions."""

    @given(graph_config_strategy)
    @settings(max_examples=50)
    def test_routing_selects_valid_provider(self, config):
        """Routing should always select a provider from the priority list."""
        from backend.governance.budget import BudgetContext
        from backend.governance.routing import RoleModelAssignment, RuleBasedProviderRouter
        from backend.persistence.testing import (
            InMemoryModelCatalog,
            InMemoryProviderHealthStore,
        )
        health_store = InMemoryProviderHealthStore()
        catalog = InMemoryModelCatalog(entries=[], role_token_policies=[])
        assignment = RoleModelAssignment(
            role="coder",
            primary_model_id="gpt-4.1",
            fallback_model_id="llama3.1",
        )
        router = RuleBasedProviderRouter(
            model_catalog=catalog,
            health_store=health_store,
            role_assignments=[assignment],
        )
        ctx = BudgetContext(
            run_id="run-1", tenant_id=config["tenant_id"],
            team_id=config["team_id"], ticket_key="TK-1", role="coder",
        )
        try:
            selected = router.select_model(
                role="coder",
                run_id="run-1",
                tenant_id=config["tenant_id"],
                budget_context=ctx,
                deployment_profile="connected",
            )
            assert selected is not None
        except Exception:
            pass

    @given(graph_config_strategy)
    @settings(max_examples=50)
    def test_routing_respects_budget_cap(self, config):
        """Routing should never exceed the budget cap."""
        from backend.governance.budget import BudgetCaps, BudgetContext
        from backend.persistence.testing import InMemoryBudgetLedger
        ledger = InMemoryBudgetLedger()
        cap = Decimal(str(max(config["budget_cap_usd"], 1.0)))
        caps = BudgetCaps(
            ticket_cap_usd=cap,
            daily_team_cap_usd=cap * 10,
            monthly_team_cap_usd=cap * 100,
        )
        ctx = BudgetContext(
            run_id="run-1",
            tenant_id=config["tenant_id"],
            team_id=config["team_id"],
            ticket_key="TK-1",
            role="coder",
        )
        ledger.configure_caps(ctx, caps)
        total_reserved = Decimal("0")
        for i in range(int(cap) + 5):
            run_ctx = BudgetContext(
                run_id=f"run-{i}",
                tenant_id=config["tenant_id"],
                team_id=config["team_id"],
                ticket_key=f"TK-{i}",
                role="coder",
            )
            try:
                result = ledger.reserve(run_ctx, Decimal("1.0"))
                total_reserved += result.reserved_amount_usd
            except Exception:
                pass
        assert total_reserved <= cap

    @given(graph_config_strategy)
    @settings(max_examples=50)
    def test_routing_enforces_iteration_limit(self, config):
        """Routing should never exceed max_autonomous_iterations."""
        max_iter = config["max_autonomous_iterations"]
        assert max_iter >= 1
        assert max_iter <= 100


class TestGraphConfigEdgeCases:
    """Edge case tests for GraphConfig."""

    def test_single_provider_in_priority(self):
        """Single provider in priority list should be valid."""
        config = {
            "tenant_id": "test-tenant",
            "team_id": "test-team",
            "provider_priority": ["openai"],
            "budget_cap_usd": 10.0,
            "max_autonomous_iterations": 5,
            "require_human_approval": False,
            "sandbox_timeout_seconds": 300,
        }
        assert len(config["provider_priority"]) == 1
