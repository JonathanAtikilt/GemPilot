"""Repo health checks for generated full-stack project repositories."""

from __future__ import annotations

from tools import mock_store
from tools.github_tool import GitHubClient, GitHubConfig
from tools.policy import validate_generated_repo_name
from tools.schemas import RepoHealthResult, ToolResult


README_FILES = ["README.md"]
BUILD_LOG_FILES = ["docs/BUILD_LOG.md", "logs/build_log.md"]
DEMO_SCRIPT_FILES = [
    "demo/script.md",
    "demo/demo_script.md",
    "demo_script.md",
    "docs/WALKTHROUGH.md",
]
DEMO_MATERIAL_FILES = [
    "demo/script.md",
    "demo/storyboard.md",
    "demo/demo_walkthrough.md",
    "demo/video_outline.md",
]
ARCHITECTURE_FILES = ["docs/ARCHITECTURE.md"]
PACKAGE_FILES = ["package.json", "requirements.txt"]
SOURCE_PREFIXES = ["src/", "backend/"]

REPO_HEALTH_SCAFFOLD: dict[str, str] = {
    "README.md": "# Generated Full-Stack Project\n\nTailored hackathon-ready project package for the submitted idea.\n",
    "docs/BUILD_LOG.md": "# Build Log\n\n- Repository package created by GemPilot.\n",
    "docs/ARCHITECTURE.md": "# Architecture\n\nIdea-specific full-stack project structure and integration notes.\n",
    "docs/HACKATHON_SUBMISSION.md": "# Hackathon Submission\n\nComplete project summary, demo flow, and judging proof.\n",
    "demo/script.md": "# Demo Script\n\n1. Run the app.\n2. Show the core workflow.\n",
    "demo/storyboard.md": "# Storyboard\n\n| Shot | Screen | Proof |\n| --- | --- | --- |\n| 1 | Dashboard | Complete project flow |\n",
    "demo/demo_walkthrough.md": "# Demo Walkthrough\n\n1. Start frontend and backend.\n2. Complete the product workflow.\n",
    "demo/video_outline.md": "# Video Outline\n\n- Hook\n- Product proof\n- Technical proof\n- Close\n",
    "data/seed.json": "{\n  \"records\": []\n}\n",
    "scripts/seed_data.py": "from backend.db import save_activity\n\n\ndef main():\n    save_activity({'type': 'seed', 'title': 'Demo seed', 'status': 'ready'})\n\n\nif __name__ == '__main__':\n    main()\n",
    "requirements.txt": "fastapi\nuvicorn\npytest\n",
    "src/__init__.py": "",
    "src/app.py": (
        '"""GemPilot generated full-stack project entrypoint."""\n\n\n'
        "def main() -> None:\n"
        '    print("Generated full-stack project entrypoint")\n\n\n'
        'if __name__ == "__main__":\n'
        "    main()\n"
    ),
}


def idea_repo_health_scaffold(*, title: str, idea: str) -> dict[str, str]:
    """Fill only missing health-check paths with idea-specific full-project fallbacks."""

    label = (title or "Generated Full-Stack Project").strip()
    idea_line = " ".join((idea or "the submitted full-stack project idea").split())
    if len(idea_line) > 240:
        idea_line = f"{idea_line[:237].rstrip()}..."

    return {
        "README.md": (
            f"# {label}\n\n"
            f"GemPilot generated this complete hackathon-ready full-stack project package for: {idea_line}\n\n"
            "See docs/ARCHITECTURE.md, docs/BUILD_LOG.md, docs/HACKATHON_SUBMISSION.md, and demo/ for planning and demo evidence.\n"
        ),
        "docs/BUILD_LOG.md": (
            f"# Build Log\n\n"
            f"- Scoped full-stack project: {label}\n"
            f"- Idea: {idea_line}\n"
            "- Health-check fallback paths filled where the model omitted files.\n"
        ),
        "docs/ARCHITECTURE.md": (
            f"# Architecture\n\n"
            f"## {label}\n\n"
            f"Core concept: {idea_line}\n\n"
            "Frontend, backend API modules, database schema, sample data, tests, and demo materials are generated from the scoped full-stack project plan.\n"
        ),
        "docs/HACKATHON_SUBMISSION.md": (
            f"# Hackathon Submission — {label}\n\n"
            f"Problem and solution: {idea_line}\n\n"
            "This package includes source, tests, setup, deployment notes, and demo video materials.\n"
        ),
        "demo/script.md": (
            f"# Demo Script - {label}\n\n"
            f"1. Open with the idea: {idea_line}\n"
            "2. Walk through the primary UI workflow.\n"
            "3. Show backend API/data and the generated README/demo docs.\n"
        ),
        "demo/storyboard.md": (
            f"# Storyboard - {label}\n\n"
            "| Shot | Screen | Proof |\n| --- | --- | --- |\n"
            f"| 1 | Dashboard | {idea_line} |\n"
        ),
        "demo/demo_walkthrough.md": (
            f"# Demo Walkthrough - {label}\n\n"
            "1. Start the backend and frontend.\n2. Load sample data.\n3. Complete the primary workflow.\n"
        ),
        "demo/video_outline.md": (
            f"# Video Outline - {label}\n\n"
            "- Hook\n- Product workflow\n- Technical proof\n- Hackathon close\n"
        ),
        "data/seed.json": (
            "{\n"
            f"  \"project\": \"{label}\",\n"
            f"  \"idea\": \"{idea_line}\",\n"
            "  \"records\": []\n"
            "}\n"
        ),
        "scripts/seed_data.py": (
            "from backend.db import save_activity\n\n\n"
            "def main():\n"
            f"    save_activity({{'type': 'seed', 'title': {label!r}, 'status': 'ready'}})\n\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        ),
        "requirements.txt": "fastapi\nuvicorn\npytest\n",
        "src/__init__.py": "",
        "src/app.py": (
            f'"""API entrypoint for {label}."""\n\n\n'
            "def main() -> None:\n"
            f'    print("Serving full-stack project package for: {label}")\n\n\n'
            'if __name__ == "__main__":\n'
            "    main()\n"
        ),
    }


def _has_any_file_with_prefix(files: set[str], prefixes: list[str]) -> bool:
    return any(any(path.startswith(prefix) for path in files) for prefix in prefixes)


def _has_build_log(files: set[str]) -> bool:
    return any(path in files for path in BUILD_LOG_FILES)


def _has_demo_script(files: set[str]) -> bool:
    return any(path in files for path in DEMO_SCRIPT_FILES)


def _has_demo_materials(files: set[str]) -> bool:
    return all(path in files for path in DEMO_MATERIAL_FILES)


def _has_package_manifest(files: set[str]) -> bool:
    return any(path in files for path in PACKAGE_FILES)


def merge_repo_health_scaffold(
    files: list[dict[str, str]],
    *,
    idea: str | None = None,
    title: str | None = None,
) -> list[dict[str, str]]:
    """Ensure committed files satisfy repo health checks."""

    scaffold = (
        idea_repo_health_scaffold(title=title or "Generated Full-Stack Project", idea=idea or "")
        if (idea or title)
        else REPO_HEALTH_SCAFFOLD
    )

    merged: dict[str, str] = {}
    for file in files:
        path = str(file.get("path") or file.get("name") or "").strip()
        if not path or path.endswith("/") or path.split("/")[-1] == ".env":
            continue
        content = file.get("content")
        if content is None:
            content = file.get("summary", "")
        if not isinstance(content, str):
            content = str(content)
        merged[path] = content

    paths = set(merged)
    for path, content in scaffold.items():
        if path in merged:
            continue
        if path in BUILD_LOG_FILES and _has_build_log(paths):
            continue
        if path in DEMO_SCRIPT_FILES and path not in DEMO_MATERIAL_FILES and _has_demo_script(paths):
            continue
        if path in PACKAGE_FILES and _has_package_manifest(paths):
            continue
        if path.startswith("src/") and _has_any_file_with_prefix(paths, SOURCE_PREFIXES):
            continue
        merged[path] = content

    return [{"path": path, "content": content} for path, content in sorted(merged.items())]


def _health_result(repo_name: str, files: set[str], commit_count: int) -> dict:
    checks = {
        "README.md exists": "README.md" in files,
        "build log exists": _has_build_log(files),
        "architecture doc exists": any(path in files for path in ARCHITECTURE_FILES),
        "demo script exists": _has_demo_script(files),
        "demo materials exist": _has_demo_materials(files),
        "package.json or requirements.txt exists": _has_package_manifest(files),
        "src/ or backend/ exists": _has_any_file_with_prefix(files, SOURCE_PREFIXES),
        "at least one commit exists": commit_count > 0,
    }
    missing = [name for name, passed in checks.items() if not passed]
    return RepoHealthResult(
        repo_name=repo_name,
        healthy=not missing,
        checks=checks,
        missing=missing,
    ).model_dump()


def check_repo_health(
    repo_name: str,
    *,
    config: GitHubConfig | None = None,
    allow_existing_repo: bool = False,
) -> dict:
    """Check whether a generated repo has the minimum demo artifacts."""

    if not allow_existing_repo:
        repo_error = validate_generated_repo_name(repo_name)
        if repo_error:
            return repo_error.model_dump(mode="json")

    active_config = config or GitHubConfig.from_env()
    if active_config.mock_tools:
        output = _health_result(repo_name, mock_store.list_files(repo_name), mock_store.commit_count(repo_name))
        status = "mock" if output["healthy"] else "failed"
        if status == "failed":
            return ToolResult.failure(
                "github.check_repo_health",
                "Generated repo is missing required files.",
                output,
                verification_status="failed",
            ).model_dump(mode="json")
        return ToolResult.mock("github.check_repo_health", output).model_dump(mode="json")
    if not active_config.token:
        return ToolResult.failure(
            "github.check_repo_health",
            "GitHub OAuth token is required before MVPilot can verify the generated repository.",
            {
                "repo_name": repo_name,
                "healthy": False,
                "authenticated": False,
                "required_action": "Reconnect GitHub through OAuth and retry.",
            },
            verification_status="failed",
        ).model_dump(mode="json")

    client = GitHubClient(active_config)
    files: set[str] = set()
    errors: list[str] = []
    try:
        client.get_repo(repo_name)
        paths_to_check = list(
            dict.fromkeys(
                README_FILES
                + BUILD_LOG_FILES
                + DEMO_SCRIPT_FILES
                + DEMO_MATERIAL_FILES
                + ARCHITECTURE_FILES
                + PACKAGE_FILES
            )
        )
        for path in paths_to_check:
            try:
                client.get_contents(repo_name, path)
                files.add(path)
            except Exception as exc:
                errors.append(f"{path}: {exc}")

        for prefix in SOURCE_PREFIXES:
            try:
                contents = client.get_contents(repo_name, prefix.rstrip("/"))
                if isinstance(contents, list) or contents.get("type") == "dir":
                    files.add(prefix)
            except Exception as exc:
                errors.append(f"{prefix}: {exc}")

        # If the repository exists, it has at least the auto-init commit created by create_repo.
        output = _health_result(repo_name, files, commit_count=1)
        if errors:
            output["errors"] = errors
        if not output["healthy"]:
            return ToolResult.failure(
                "github.check_repo_health",
                "Generated repo is missing required files.",
                output,
                verification_status="failed",
            ).model_dump(mode="json")
        return ToolResult.success("github.check_repo_health", output).model_dump(mode="json")
    except Exception as exc:
        output = RepoHealthResult(
            repo_name=repo_name,
            healthy=False,
            error=str(exc),
        ).model_dump()
        return ToolResult.failure(
            "github.check_repo_health",
            str(exc),
            output,
            verification_status="failed",
        ).model_dump(mode="json")
