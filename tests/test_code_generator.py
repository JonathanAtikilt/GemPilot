from __future__ import annotations

from agent.code_generator import _generation_stages


def test_generation_stages_for_cli_skips_database_and_frontend() -> None:
    stages = _generation_stages(
        {
            "implementation_stages": ["cli_core", "commands", "tests", "docs", "demo"],
        },
        {"database_required": False, "backend_required": True, "frontend_required": False},
    )
    assert "database" not in stages
    assert "frontend" not in stages
    assert "backend" in stages
    assert stages[-2:] == ("docs", "demo")


def test_generation_stages_for_web_app_keeps_full_stack() -> None:
    stages = _generation_stages(
        {
            "implementation_stages": ["database", "backend", "frontend", "tests", "docs", "demo"],
            "validation_profile": {
                "check_database_models": True,
                "check_backend_routes": True,
                "check_frontend_routes": True,
            },
        },
        {"database_required": True, "backend_required": True, "frontend_required": True},
    )
    assert stages == ("database", "backend", "frontend", "docs", "demo")
