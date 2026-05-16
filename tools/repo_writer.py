"""Repository writing helpers for generated MVP artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tools import mock_store
from tools.github_tool import GitHubClient, GitHubConfig, commit_files
from tools.policy import validate_github_mutation
from tools.schemas import ToolResult


BUILD_LOG_PATH = "logs/build_log.md"
BUILD_LOG_RETRY_LIMIT = 1


def _format_log_entry(task_id: str, message: str, data: dict[str, Any]) -> str:
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    metadata = f" | data={data}" if data else ""
    return f"- {timestamp} | task={task_id} | {message}{metadata}\n"


def append_build_log(task_id: str, repo_name: str, message: str, data: dict) -> dict:
    """Append an entry to `logs/build_log.md` and verify the update is readable."""

    if not task_id.strip():
        return ToolResult.failure("github.append_build_log", "task_id must not be empty.").model_dump(mode="json")
    if not message.strip():
        return ToolResult.failure("github.append_build_log", "Build log message must not be empty.").model_dump(mode="json")

    policy_error = validate_github_mutation("append_build_log", repo_name, [{"path": BUILD_LOG_PATH, "content": ""}])
    if policy_error:
        return policy_error.model_dump(mode="json")

    entry = _format_log_entry(task_id, message.strip(), data)
    config = GitHubConfig.from_env()

    if config.mock_tools or not config.token:
        existing = mock_store.get_file(repo_name, BUILD_LOG_PATH) or "# MVPilot Build Log\n\n"
        updated = existing + entry
        commit = mock_store.commit_files(repo_name, {BUILD_LOG_PATH: updated}, f"Update build log: {message.strip()}")
        verified_content = mock_store.get_file(repo_name, BUILD_LOG_PATH) or ""
        verified = entry in verified_content
        output = {
            "repo_name": repo_name,
            "path": BUILD_LOG_PATH,
            "commit_sha": commit.sha,
            "entry": entry.strip(),
            "verified": verified,
        }
        if not verified:
            return ToolResult.failure(
                "github.append_build_log",
                "Build log append could not be verified in mock store.",
                output,
                verification_status="failed",
            ).model_dump(mode="json")
        return ToolResult.mock("github.append_build_log", output).model_dump(mode="json")

    client = GitHubClient(config)
    last_error: str | None = None
    for attempt in range(BUILD_LOG_RETRY_LIMIT + 1):
        try:
            try:
                existing = client.get_file_text(repo_name, BUILD_LOG_PATH) or "# MVPilot Build Log\n\n"
            except Exception:
                existing = "# MVPilot Build Log\n\n"

            updated = existing + entry
            commit_result = commit_files(
                repo_name,
                [{"path": BUILD_LOG_PATH, "content": updated}],
                f"Update build log: {message.strip()}",
            )
            if commit_result["status"] not in {"success", "mock"}:
                last_error = commit_result.get("error") or "Build log commit failed."
                if attempt < BUILD_LOG_RETRY_LIMIT:
                    continue
                return commit_result

            verified_content = client.get_file_text(repo_name, BUILD_LOG_PATH) or ""
            verified = entry in verified_content
            output = {
                "repo_name": repo_name,
                "path": BUILD_LOG_PATH,
                "commit_sha": commit_result["output"].get("commit_sha"),
                "entry": entry.strip(),
                "verified": verified,
                "attempts": attempt + 1,
            }
            if not verified:
                last_error = "Build log append was committed but could not be verified."
                if attempt < BUILD_LOG_RETRY_LIMIT:
                    continue
                return ToolResult.failure(
                    "github.append_build_log",
                    last_error,
                    output,
                    verification_status="failed",
                ).model_dump(mode="json")
            return ToolResult.success("github.append_build_log", output).model_dump(mode="json")
        except Exception as exc:
            last_error = str(exc)
            if attempt >= BUILD_LOG_RETRY_LIMIT:
                break

    return ToolResult.failure(
        "github.append_build_log",
        last_error or "Build log append failed.",
        {"repo_name": repo_name, "path": BUILD_LOG_PATH, "attempts": BUILD_LOG_RETRY_LIMIT + 1},
    ).model_dump(mode="json")
