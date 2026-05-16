from agent.generated_project import (
    build_project_artifacts,
    merge_with_project_artifacts,
    title_from_idea,
)


def test_title_from_idea_strips_build_prefix() -> None:
    assert title_from_idea("Build a study planner for students").startswith("Study planner")


def test_build_project_artifacts_includes_runnable_stack() -> None:
    artifacts = build_project_artifacts(
        idea="Build a referral coordinator",
        title="Referral Coordinator",
        resolved_stack="React, FastAPI, Supabase",
    )
    names = {artifact["name"] for artifact in artifacts}
    assert "README.md" in names
    assert "package.json" in names
    assert "src/App.jsx" in names
    assert "backend/main.py" in names
    assert "docs/BUILD_LOG.md" in names
    assert "demo/demo_script.md" in names


def test_merge_with_project_artifacts_keeps_model_files() -> None:
    merged = merge_with_project_artifacts(
        [{"name": "custom/feature.md", "kind": "markdown", "content": "# Custom", "summary": "extra"}],
        idea="Build a planner",
        title="Planner",
        resolved_stack="React",
    )
    names = {artifact["name"] for artifact in merged}
    assert "custom/feature.md" in names
    assert "package.json" in names
