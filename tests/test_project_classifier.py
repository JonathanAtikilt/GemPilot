from __future__ import annotations

import pytest

from agent.project_classifier import ProjectClassifier, classify_project


@pytest.mark.parametrize(
    ("idea", "expected_category"),
    [
        ("Build a Chrome extension that summarizes articles", "browser_extension"),
        ("CLI tool to batch rename photos from the terminal", "cli_tool"),
        ("Personal portfolio website for my design work", "portfolio_website"),
        ("Realtime multiplayer trivia game with lobbies", "multiplayer_game"),
        ("Marketplace for vintage furniture buyers and sellers", "marketplace"),
        ("Research platform for organizing papers and citations", "research_platform"),
        ("REST API service for webhook delivery", "api_service"),
        ("Sports analytics dashboard for youth soccer teams", "sports_analytics"),
    ],
)
def test_classifier_detects_diverse_categories(idea: str, expected_category: str) -> None:
    profile = classify_project(idea)
    assert profile.category == expected_category


def test_classifier_cli_has_no_frontend() -> None:
    profile = classify_project("A command-line utility to lint Python projects")
    assert profile.frontend_required is False
    assert profile.category == "cli_tool"


def test_classifier_api_service_skips_frontend() -> None:
    profile = classify_project(
        "API-only microservice for image resizing",
        intake={"targetPlatform": "api"},
    )
    assert profile.category == "api_service"
    assert profile.frontend_required is False
    assert profile.backend_required is True


def test_classifier_multiplayer_requires_realtime() -> None:
    profile = classify_project("Multiplayer online card game with matchmaking")
    assert profile.realtime_required is True
    assert profile.category == "multiplayer_game"


def test_apply_profile_merges_into_requirements() -> None:
    from agent.project_classifier import apply_profile_to_requirements

    profile = ProjectClassifier().classify("CLI backup tool")
    merged = apply_profile_to_requirements({}, profile)
    assert merged["target_platform"] == "cli tool"
    assert merged["project_profile"]["category"] == "cli_tool"
