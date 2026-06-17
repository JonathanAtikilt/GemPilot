from __future__ import annotations

from agent.architecture_planner import ArchitecturePlanner, UNIVERSAL_PATHS, plan_architecture
from agent.project_classifier import classify_project, apply_profile_to_requirements


def test_apply_profile_strips_auth_routes_for_cli() -> None:
    profile = classify_project("CLI tool to convert CSV to Parquet")
    scope = apply_profile_to_requirements(
        {
            "api_routes": ["POST /api/auth/login", "GET /api/data"],
            "advanced_features": ["Role-aware authenticated workspace"],
        },
        profile,
    )
    assert profile.category == "cli_tool"
    assert scope["api_routes"] == []
    assert scope["advanced_features"] == []


def test_planner_cli_tree_has_no_react_app() -> None:
    profile = classify_project("CLI tool to convert CSV to Parquet")
    plan = plan_architecture(profile)
    paths = set(plan.file_tree)
    assert "commands/run.py" in paths
    assert "utils/parser.py" in paths
    assert "src/App.jsx" not in paths
    assert "backend/main.py" not in paths


def test_planner_extension_tree() -> None:
    profile = classify_project("Browser extension for tab management")
    plan = plan_architecture(profile)
    assert "manifest.json" in plan.file_tree
    assert "background/service_worker.js" in plan.file_tree
    assert "popup/popup.js" in plan.file_tree


def test_planner_api_only_tree() -> None:
    profile = classify_project("REST API for scheduling jobs", intake={"targetPlatform": "api"})
    plan = plan_architecture(profile)
    assert "backend/main.py" in plan.file_tree
    assert "src/App.jsx" not in plan.file_tree


def test_architecture_plan_to_repo_plan_shape() -> None:
    from agent.architecture_planner import architecture_plan_to_repo_plan

    profile = classify_project("Sports analytics dashboard for basketball")
    plan = plan_architecture(profile)
    repo = architecture_plan_to_repo_plan(plan)
    assert repo["file_tree"]
    assert "validation_profile" in repo


def _structural_signature(plan) -> frozenset[str]:
    """Implementation paths excluding universal docs/demo artifacts."""
    return frozenset(
        path
        for path in plan.file_tree
        if path not in UNIVERSAL_PATHS and not path.startswith("docs/") and not path.startswith("demo/")
    )


def test_diverse_blueprints_are_structurally_different() -> None:
    ideas = [
        "Chrome extension that blocks distracting sites",
        "CLI tool to grep logs and summarize errors",
        "Portfolio website for a photographer",
        "Multiplayer realtime puzzle game",
        "Marketplace for handmade crafts",
        "Research platform for lab notes",
        "API-only webhook router service",
        "Sports analytics dashboard for tennis",
    ]
    planner = ArchitecturePlanner()
    fingerprints: list[frozenset[str]] = []
    for idea in ideas:
        profile = classify_project(idea)
        plan = planner.plan(profile)
        fingerprints.append(_structural_signature(plan) | frozenset(plan.entrypoints))

    for i, left in enumerate(fingerprints):
        for j, right in enumerate(fingerprints):
            if i >= j:
                continue
            overlap = len(left & right) / max(len(left | right), 1)
            assert overlap < 0.85, f"Architectures too similar: ideas {i} and {j} overlap={overlap:.2f}"
