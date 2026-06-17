from __future__ import annotations

from agent.adaptive_validation import validate_project_adaptive
from agent.project_classifier import classify_project, apply_profile_to_requirements


def _cli_artifacts() -> list[dict[str, str]]:
    return [
        {"name": "README.md", "content": "# DataCLI\n\nPython CLI for ingesting CSV files.\n\n## Setup\npip install .\n## Features\n- ingest\n## Demo\ndemo/script.md"},
        {"name": "cli/main.py", "content": "from cli.runner import run\nif __name__ == '__main__': run()"},
        {"name": "cli/runner.py", "content": "def run():\n    print('ingesting csv')"},
        {"name": "cli/__init__.py", "content": ""},
        {"name": "docs/ARCHITECTURE.md", "content": "# Architecture\nCLI tool for CSV ingestion."},
        {"name": "docs/DEPLOY.md", "content": "# Deploy\npip install -e ."},
        {"name": "docs/PROJECT_PLAN.md", "content": "# Plan\nCSV CLI"},
        {"name": "docs/TESTING_STRATEGY.md", "content": "# Tests\npytest"},
        {"name": "demo/script.md", "content": "# Demo CSV ingestion CLI tool"},
        {"name": "demo/storyboard.md", "content": "# Storyboard CSV CLI"},
        {"name": "demo/demo_walkthrough.md", "content": "# Walkthrough ingesting CSV files"},
        {"name": "demo/video_outline.md", "content": "# Video CSV CLI demo"},
        {"name": "tests/test_cli.py", "content": "from cli.runner import run\ndef test_run(): run()"},
    ]


def test_adaptive_validation_skips_web_only_checks_for_cli() -> None:
    profile = classify_project("CLI tool to ingest CSV files")
    scope = apply_profile_to_requirements(
        {
            "core_features": ["CSV ingest", "transform", "export", "config"],
            "project_archetype": "cli_tool",
            "user_flows": [
                {"step": "1", "action": "ingest", "screen": "CLI", "api": "N/A"},
            ],
        },
        profile,
    )
    result = validate_project_adaptive(
        idea="DataCLI: Python CLI for ingesting CSV files.",
        intake={"title": "DataCLI"},
        project_requirements=scope,
        architecture_plan={"file_tree": ["cli/main.py", "README.md"]},
        generated_artifacts=_cli_artifacts(),
        model_modes=["live"],
    )
    skipped = {c["name"] for c in result["checks"] if "Skipped" in str(c.get("detail", ""))}
    assert "studypilot_benchmark_complete" not in {c["name"] for c in result["checks"]}
    assert result["project_category"] == "cli_tool"
    assert "seed_data_present" in skipped or result["passed"]
