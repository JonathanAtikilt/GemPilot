from __future__ import annotations

from agent.project_classifier import classify_for_generation
from agent.project_plan import build_project_plan


def test_classify_for_generation_schema() -> None:
    result = classify_for_generation("CLI tool to convert CSV files to JSON")
    payload = result.to_dict()
    assert set(payload) == {
        "project_type",
        "complexity",
        "frontend_needed",
        "backend_needed",
        "database_needed",
        "realtime_needed",
        "ai_needed",
        "deployment_strategy",
    }
    assert payload["project_type"] == "cli_tool"
    assert payload["frontend_needed"] is False


def test_build_project_plan_includes_required_sections() -> None:
    plan = build_project_plan(
        idea="Portfolio website for a photographer with project gallery",
        intake={"requiredFeatures": ["Project gallery", "Contact form"]},
        scope={"core_features": ["Project gallery", "Contact form"]},
    )
    data = plan.to_dict()
    assert data["project_summary"]
    assert data["target_users"]
    assert data["chosen_stack"]
    assert data["required_features"]
    assert "excluded_features" in data
    assert data["validation_rules"]
