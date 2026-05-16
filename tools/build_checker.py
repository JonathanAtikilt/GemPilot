"""Repo health checks for generated MVP repositories."""

from __future__ import annotations

from tools import mock_store
from tools.github_tool import GitHubClient, GitHubConfig
from tools.policy import validate_generated_repo_name
from tools.schemas import RepoHealthResult, ToolResult


REQUIRED_FILES = ["README.md", "logs/build_log.md", "demo/demo_script.md"]
PACKAGE_FILES = ["package.json", "requirements.txt"]
SOURCE_PREFIXES = ["src/", "backend/"]


def _has_any_file_with_prefix(files: set[str], prefixes: list[str]) -> bool:
    return any(any(path.startswith(prefix) for path in files) for prefix in prefixes)


def _health_result(repo_name: str, files: set[str], commit_count: int) -> dict:
    checks = {
        "README.md exists": "README.md" in files,
        "logs/build_log.md exists": "logs/build_log.md" in files,
        "demo/demo_script.md exists": "demo/demo_script.md" in files,
        "package.json or requirements.txt exists": any(path in files for path in PACKAGE_FILES),
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
) -> dict:
    """Check whether a generated repo has the minimum demo artifacts."""

    repo_error = validate_generated_repo_name(repo_name)
    if repo_error:
        return repo_error.model_dump(mode="json")

    active_config = config or GitHubConfig.from_env()
    if active_config.mock_tools or not active_config.token:
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

    client = GitHubClient(active_config)
    files: set[str] = set()
    errors: list[str] = []
    try:
        client.get_repo(repo_name)
        for path in REQUIRED_FILES + PACKAGE_FILES:
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
