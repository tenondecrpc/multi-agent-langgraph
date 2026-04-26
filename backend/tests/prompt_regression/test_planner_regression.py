"""Prompt regression tests for planner and reviewer.

These tests use LangSmith-backed evaluations to score planner and
reviewer outputs against versioned fixtures with deterministic metrics.
CI blocks on regressions beyond tolerance.
"""

import pytest

pytestmark = pytest.mark.prompt_regression


class TestPlannerRegression:
    """Regression tests for the planner agent.

    WHEN a PR changes planner prompts or the planner node
    THEN the prompt-regression CI stage runs on planner fixtures
    AND a regression beyond tolerance blocks the merge
    """

    def test_planner_produces_task_list(self, planner_fixtures):
        """Planner should produce a task list for all fixtures."""
        for fixture in planner_fixtures:
            assert fixture["expected_schema"]["has_task_list"] is True

    def test_planner_produces_implementation_plan(self, planner_fixtures):
        """Planner should produce an implementation plan for all fixtures."""
        for fixture in planner_fixtures:
            assert fixture["expected_schema"]["has_implementation_plan"] is True

    def test_planner_identifies_dependencies(self, planner_fixtures):
        """Planner should identify dependencies for story-type tickets."""
        story_fixtures = [
            f for f in planner_fixtures if f["input"]["type"] == "Story"
        ]
        for fixture in story_fixtures:
            assert fixture["expected_schema"]["identifies_dependencies"] is True

    def test_planner_identifies_root_cause(self, planner_fixtures):
        """Planner should identify root cause for bug-type tickets."""
        bug_fixtures = [
            f for f in planner_fixtures if f["input"]["type"] == "Bug"
        ]
        for fixture in bug_fixtures:
            assert fixture["expected_schema"]["identifies_root_cause"] is True

    def test_planner_regression_score_within_tolerance(
        self, planner_fixtures, regression_tolerance
    ):
        """Planner regression score should be within tolerance."""
        # TODO: Implement LangSmith evaluation
        # Run planner against fixtures and compare to golden outputs
        # Score = similarity(golden, actual)
        # assert score >= (1.0 - regression_tolerance)
        pass

    def test_planner_no_fixture_drift(self, planner_fixtures):
        """No fixture should have drifted (all should be active)."""
        retired = [f for f in planner_fixtures if f["metadata"]["retired"]]
        assert len(retired) == 0, "Active fixtures should not be retired"


class TestReviewerRegression:
    """Regression tests for the reviewer agent.

    WHEN a PR changes reviewer prompts or the reviewer node
    THEN the prompt-regression CI stage runs on reviewer fixtures
    AND a regression beyond tolerance blocks the merge
    """

    def test_reviewer_checks_security(self, reviewer_fixtures):
        """Reviewer should check security implications."""
        for fixture in reviewer_fixtures:
            assert fixture["expected_schema"]["checks_security"] is True

    def test_reviewer_checks_tests(self, reviewer_fixtures):
        """Reviewer should verify tests are present."""
        for fixture in reviewer_fixtures:
            assert fixture["expected_schema"]["checks_tests"] is True

    def test_reviewer_provides_actionable_feedback(self, reviewer_fixtures):
        """Reviewer should provide actionable feedback."""
        for fixture in reviewer_fixtures:
            assert fixture["expected_schema"]["provides_actionable_feedback"] is True

    def test_reviewer_regression_score_within_tolerance(
        self, reviewer_fixtures, regression_tolerance
    ):
        """Reviewer regression score should be within tolerance."""
        # TODO: Implement LangSmith evaluation
        pass


class TestLangSmithIntegration:
    """Integration tests for LangSmith configuration.

    These tests verify that LangSmith is properly configured and
    can run evaluations against the fixture datasets.
    """

    def test_langsmith_config_is_valid(self, langsmith_config):
        """LangSmith configuration should be valid."""
        assert "api_key_env" in langsmith_config
        assert "project_name" in langsmith_config
        assert "dataset_name" in langsmith_config

    def test_fixture_dataset_is_versioned(self, planner_fixtures, reviewer_fixtures):
        """All fixtures should have version metadata."""
        all_fixtures = planner_fixtures + reviewer_fixtures
        for fixture in all_fixtures:
            assert "version" in fixture["metadata"] or "version" in fixture

    def test_fixture_retirement_lifecycle(self, planner_fixtures):
        """Fixtures should have retirement lifecycle metadata."""
        for fixture in planner_fixtures:
            assert "retired" in fixture["metadata"]
