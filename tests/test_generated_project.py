from agent.generated_project import (
    build_project_artifacts,
    merge_with_project_artifacts,
    title_from_idea,
)
from agent.project_generation import hydrate_file_manifest


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
    assert "src/App.jsx" in names or "frontend/src/App.jsx" in names
    assert "backend/main.py" in names
    assert "docs/BUILD_LOG.md" in names
    assert "docs/WALKTHROUGH.md" in names
    assert "data/seed.json" in names


def test_build_project_artifacts_includes_hackathon_files_when_enabled() -> None:
    artifacts = build_project_artifacts(
        idea="Build a referral coordinator",
        title="Referral Coordinator",
        resolved_stack="React, FastAPI, Supabase",
        is_hackathon_mode=True,
    )
    names = {artifact["name"] for artifact in artifacts}
    assert {"demo/script.md", "demo/storyboard.md", "demo/demo_walkthrough.md", "demo/video_outline.md"} <= names
    assert "docs/HACKATHON_SUBMISSION.md" in names


def test_hydrate_file_manifest_gap_fills_universal_docs_only() -> None:
    artifacts = hydrate_file_manifest(
        [{"name": "README.md", "kind": "markdown", "summary": "Gemini overview.", "content": "# StudyPilot\n\nGemini draft."}],
        idea="Build StudyPilot for college students.",
        title="StudyPilot",
        resolved_stack="React, FastAPI",
        project_requirements={"must_have": ["weekly plan"], "target_platform": "web app"},
        architecture_plan={"file_tree": ["src/App.jsx", "backend/main.py", "README.md"]},
    )
    readme = next(item for item in artifacts if item["name"] == "README.md")
    assert readme["content"] == "# StudyPilot\n\nGemini draft."
    assert readme["summary"] == "Gemini overview."
    assert not any(item["name"] == "demo/script.md" for item in artifacts)
    assert not any(item["name"] == "backend/main.py" for item in artifacts)


def test_hydrate_file_manifest_gap_fills_hackathon_docs_when_enabled() -> None:
    artifacts = hydrate_file_manifest(
        [{"name": "README.md", "kind": "markdown", "summary": "Gemini overview.", "content": "# StudyPilot\n\nGemini draft."}],
        idea="Build StudyPilot for college students.",
        title="StudyPilot",
        resolved_stack="React, FastAPI",
        project_requirements={"must_have": ["weekly plan"], "target_platform": "web app"},
        architecture_plan={"file_tree": ["src/App.jsx", "backend/main.py", "README.md"]},
        is_hackathon_mode=True,
    )
    assert any(item["name"] == "demo/script.md" for item in artifacts)


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
