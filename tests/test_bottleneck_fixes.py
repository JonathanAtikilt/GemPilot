"""Verify classifier decisions propagate into generated project artifacts."""

from __future__ import annotations

import re

import pytest

from agent.generated_project import build_project_artifacts, _api_client

STUDY_ROUTE_MARKERS = (
    "/api/uploads",
    "/api/files/upload",
    "/api/summaries",
    "/api/quizzes",
    "/api/flashcards/review",
    "/api/study-plan",
    "/api/progress",
)


def _by_name(artifacts: list[dict[str, str]]) -> dict[str, str]:
    return {item["name"]: item["content"] for item in artifacts}


def _backend_main(artifacts: list[dict[str, str]]) -> str:
    return _by_name(artifacts).get("backend/main.py", "")


def _assert_no_study_routes(content: str) -> None:
    for marker in STUDY_ROUTE_MARKERS:
        assert marker not in content, f"unexpected study route {marker}"


def _assert_no_hackathon_files(names: set[str]) -> None:
    hackathon_paths = {
        "docs/HACKATHON_SUBMISSION.md",
        "demo/script.md",
        "demo/storyboard.md",
        "demo/demo_walkthrough.md",
        "demo/video_outline.md",
        "demo/voiceover.md",
    }
    assert not hackathon_paths & names


@pytest.mark.parametrize(
    ("idea", "target_platform", "expectations"),
    [
        (
            "Build a Chrome browser extension that highlights citations on research pages",
            "browser extension",
            {
                "has": {"manifest.json", "background.js", "content.js"},
                "missing": {"backend/main.py", "src/App.jsx", "package.json"},
                "auth": False,
                "database": False,
            },
        ),
        (
            "Build a CLI tool that batch-renames photo files from EXIF metadata",
            "cli tool",
            {
                "has": {"cli/main.py"},
                "missing": {"backend/main.py", "src/App.jsx", "extension/manifest.json"},
                "auth": False,
                "database": False,
            },
        ),
        (
            "Build a personal portfolio website showcasing design projects",
            "portfolio",
            {
                "has": {"frontend/index.html"},
                "missing": {"backend/main.py", "src/App.jsx", "App.tsx"},
                "auth": False,
                "database": False,
            },
        ),
        (
            "Build a REST API service for webhook ingestion and event replay",
            "api",
            {
                "has": {"backend/main.py", "tests/test_api.py"},
                "missing": {"src/App.jsx", "package.json", "App.tsx", "extension/manifest.json"},
                "auth": False,
                "database": False,
            },
        ),
        (
            "Build a React Native mobile app for tracking daily habits",
            "mobile app",
            {
                "has": {"App.tsx", "index.js", "package.json"},
                "missing": {"src/App.jsx", "backend/main.py", "extension/manifest.json", "manifest.json"},
                "auth": False,
                "database": None,
            },
        ),
        (
            "Build a marketplace where vendors list handmade goods and buyers checkout",
            "web app",
            {
                "has": {"src/App.jsx", "backend/main.py", "backend/db.py"},
                "missing": {"App.tsx", "extension/manifest.json", "cli/main.py"},
                "auth": True,
                "database": True,
            },
        ),
    ],
)
def test_generated_projects_respect_classification(
    idea: str,
    target_platform: str,
    expectations: dict,
) -> None:
    artifacts = build_project_artifacts(
        idea=idea,
        title=None,
        resolved_stack="React, FastAPI, Supabase",
        target_platform=target_platform,
        is_hackathon_mode=False,
    )
    names = {item["name"] for item in artifacts}
    contents = _by_name(artifacts)

    for path in expectations["has"]:
        assert path in names, f"expected {path} for {target_platform}"

    for path in expectations["missing"]:
        assert path not in names, f"did not expect {path} for {target_platform}"

    _assert_no_hackathon_files(names)

    backend = _backend_main(artifacts)
    if backend:
        _assert_no_study_routes(backend)

    if "App.tsx" in names:
        assert "react-native" in contents["package.json"].lower()

    if "manifest.json" in names and "backend/main.py" not in names:
        assert "manifest_version" in contents["manifest.json"].lower()

    if "cli/main.py" in names:
        assert "argparse" in contents["cli/main.py"] or "click" in contents["cli/main.py"]

    if not expectations["auth"]:
        assert "/api/auth/" not in backend
    if expectations.get("database") is False:
        assert "backend/db.py" not in names
        assert "docs/DATABASE_SCHEMA.sql" not in names
        assert "data/seed.json" not in names


def test_api_client_parses_auth_login_route() -> None:
    client = _api_client(["POST /api/auth/login", "GET /health"])
    assert "postAuthLogin" in client
    assert "postUthLogin" not in client


def test_empty_api_routes_backend_only_has_health() -> None:
    artifacts = build_project_artifacts(
        idea="Minimal API service",
        title="Minimal API",
        resolved_stack="FastAPI",
        target_platform="api",
        api_routes=[],
        is_hackathon_mode=False,
    )
    backend = _backend_main(artifacts)
    assert "@app.get('/health')" in backend
    route_defs = re.findall(r"@app\.(get|post|put|patch|delete)\(", backend)
    assert route_defs == ["get"]


def test_hackathon_files_only_when_enabled() -> None:
    off = build_project_artifacts(
        idea="Build a referral coordinator",
        title="Referral Coordinator",
        resolved_stack="React, FastAPI",
        is_hackathon_mode=False,
    )
    on = build_project_artifacts(
        idea="Build a referral coordinator",
        title="Referral Coordinator",
        resolved_stack="React, FastAPI",
        is_hackathon_mode=True,
    )
    off_names = {item["name"] for item in off}
    on_names = {item["name"] for item in on}
    _assert_no_hackathon_files(off_names)
    assert "docs/HACKATHON_SUBMISSION.md" in on_names
    assert "demo/script.md" in on_names
