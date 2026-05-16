"""GitHub tools for creating and verifying generated MVP repositories."""

from __future__ import annotations

import json
import os
from base64 import b64decode
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from tools.policy import repo_prefix, validate_github_mutation
from tools.schemas import CommitFilesRequest, CreateRepoRequest, ToolResult, safe_validation_errors
from tools import mock_store


GITHUB_API_BASE = "https://api.github.com"


@dataclass(frozen=True)
class GitHubConfig:
    token: str | None
    owner: str | None
    repo_prefix: str
    mock_tools: bool
    api_base: str = GITHUB_API_BASE

    @classmethod
    def from_env(cls) -> "GitHubConfig":
        return cls(
            token=os.getenv("GITHUB_TOKEN"),
            owner=os.getenv("GITHUB_OWNER"),
            repo_prefix=repo_prefix(),
            mock_tools=os.getenv("MVPILOT_MOCK_TOOLS", "").lower() in {"1", "true", "yes"},
        )


class GitHubClient:
    """Small REST client with centralized auth, timeout, and error handling."""

    def __init__(self, config: GitHubConfig | None = None):
        self.config = config or GitHubConfig.from_env()

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.config.mock_tools:
            raise RuntimeError("GitHubClient.request should not be called in mock mode.")
        if not self.config.token:
            raise RuntimeError("GITHUB_TOKEN is required for live GitHub mode.")

        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.config.api_base}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.config.token}",
                "Content-Type": "application/json",
                "User-Agent": "MVPilot-Person3-Tools",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        try:
            with urlopen(request, timeout=20) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            safe_body = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"GitHub API HTTP {exc.code}: {safe_body}") from exc
        except URLError as exc:
            raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc

        if not response_body:
            return {}
        return json.loads(response_body)

    def get_authenticated_user(self) -> dict[str, Any]:
        return self.request("GET", "/user")

    def get_repo(self, repo_name: str) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        return self.request("GET", f"/repos/{self.config.owner}/{repo_name}")

    def get_commit(self, repo_name: str, commit_sha: str) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        return self.request("GET", f"/repos/{self.config.owner}/{repo_name}/commits/{commit_sha}")

    def get_contents(self, repo_name: str, path: str) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        return self.request("GET", f"/repos/{self.config.owner}/{repo_name}/contents/{path}")

    def get_file_text(self, repo_name: str, path: str) -> str | None:
        contents = self.get_contents(repo_name, path)
        encoded = contents.get("content")
        if not encoded:
            return None
        return b64decode(encoded).decode("utf-8")

    def get_ref(self, repo_name: str, branch: str) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        return self.request("GET", f"/repos/{self.config.owner}/{repo_name}/git/ref/heads/{branch}")

    def create_user_repo(self, repo_name: str, description: str, private: bool) -> dict[str, Any]:
        return self.request(
            "POST",
            "/user/repos",
            {
                "name": repo_name,
                "description": description,
                "private": private,
                "auto_init": True,
            },
        )

    def create_blob(self, repo_name: str, content: str) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        return self.request(
            "POST",
            f"/repos/{self.config.owner}/{repo_name}/git/blobs",
            {"content": content, "encoding": "utf-8"},
        )

    def create_tree(
        self,
        repo_name: str,
        base_tree_sha: str,
        tree_elements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        return self.request(
            "POST",
            f"/repos/{self.config.owner}/{repo_name}/git/trees",
            {"base_tree": base_tree_sha, "tree": tree_elements},
        )

    def create_commit(self, repo_name: str, message: str, tree_sha: str, parent_sha: str) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        return self.request(
            "POST",
            f"/repos/{self.config.owner}/{repo_name}/git/commits",
            {"message": message, "tree": tree_sha, "parents": [parent_sha]},
        )

    def update_ref(self, repo_name: str, branch: str, commit_sha: str) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        return self.request(
            "PATCH",
            f"/repos/{self.config.owner}/{repo_name}/git/refs/heads/{branch}",
            {"sha": commit_sha, "force": False},
        )


def _mock_create_repo(repo_name: str, visibility: str) -> ToolResult:
    owner = os.getenv("GITHUB_OWNER", "mock-owner")
    mock_store.create_repo(repo_name)
    return ToolResult.mock(
        "github.create_repo",
        {
            "repo_name": repo_name,
            "repo_url": f"https://github.com/{owner}/{repo_name}",
            "visibility": visibility,
            "status": "created",
            "verification": "mock_repo_metadata",
        },
    )


def _mock_commit_files(request: CommitFilesRequest) -> ToolResult:
    commit = mock_store.commit_files(
        request.repo_name,
        {file.path: file.content for file in request.files},
        request.message,
    )
    return ToolResult.mock(
        "github.commit_files",
        {
            "repo_name": request.repo_name,
            "commit_sha": commit.sha,
            "message": request.message,
            "files_changed": len(request.files),
            "changed_files": commit.files_changed,
            "status": "committed",
        },
    )


def check_github_auth() -> dict:
    """Read-only preflight check for live GitHub configuration."""

    config = GitHubConfig.from_env()
    if config.mock_tools:
        return ToolResult.mock(
            "github.check_auth",
            {
                "authenticated": False,
                "owner": config.owner,
                "repo_prefix": config.repo_prefix,
                "message": "Mock mode is enabled; live GitHub auth was not checked.",
            },
        ).model_dump(mode="json")
    if not config.token:
        return ToolResult.failure(
            "github.check_auth",
            "GITHUB_TOKEN is required for live GitHub mode.",
            {"authenticated": False, "owner": config.owner, "repo_prefix": config.repo_prefix},
        ).model_dump(mode="json")
    if not config.owner:
        return ToolResult.failure(
            "github.check_auth",
            "GITHUB_OWNER is required for live GitHub mode.",
            {"authenticated": False, "repo_prefix": config.repo_prefix},
        ).model_dump(mode="json")

    client = GitHubClient(config)
    try:
        user = client.get_authenticated_user()
    except Exception as exc:
        return ToolResult.failure(
            "github.check_auth",
            str(exc),
            {"authenticated": False, "owner": config.owner, "repo_prefix": config.repo_prefix},
        ).model_dump(mode="json")

    login = user.get("login")
    return ToolResult.success(
        "github.check_auth",
        {
            "authenticated": True,
            "login": login,
            "owner": config.owner,
            "owner_matches_login": login == config.owner,
            "repo_prefix": config.repo_prefix,
        },
        verification_status="verified",
    ).model_dump(mode="json")


def create_repo(repo_name: str, description: str, visibility: str) -> dict:
    """Create a generated GitHub repository and verify it by reading metadata."""

    try:
        request = CreateRepoRequest(repo_name=repo_name, description=description, visibility=visibility)
    except ValidationError as exc:
        return ToolResult.failure(
            "github.create_repo",
            "Create repo request failed validation.",
            {"validation_error": safe_validation_errors(exc.errors(include_url=False))},
        ).model_dump(mode="json")

    policy_error = validate_github_mutation("create_repo", request.repo_name)
    if policy_error:
        return policy_error.model_dump(mode="json")

    config = GitHubConfig.from_env()
    if config.mock_tools or not config.token:
        return _mock_create_repo(request.repo_name, request.visibility).model_dump(mode="json")

    client = GitHubClient(config)
    try:
        created = client.create_user_repo(
            request.repo_name,
            request.description,
            private=request.visibility == "private",
        )
        verified = client.get_repo(request.repo_name)
    except Exception as exc:
        return ToolResult.failure("github.create_repo", str(exc)).model_dump(mode="json")

    return ToolResult.success(
        "github.create_repo",
        {
            "repo_name": request.repo_name,
            "repo_url": created.get("html_url") or verified.get("html_url"),
            "visibility": request.visibility,
            "status": "created",
            "github_id": created.get("id"),
            "verified_full_name": verified.get("full_name"),
        },
        verification_status="verified",
    ).model_dump(mode="json")


def commit_files(repo_name: str, files: list[dict], message: str) -> dict:
    """Commit multiple text files to a generated repository in one Git commit."""

    try:
        request = CommitFilesRequest(repo_name=repo_name, files=files, message=message)
    except ValidationError as exc:
        return ToolResult.failure(
            "github.commit_files",
            "Commit files request failed validation.",
            {"validation_error": safe_validation_errors(exc.errors(include_url=False))},
        ).model_dump(mode="json")

    policy_error = validate_github_mutation("commit_files", request.repo_name, request.files)
    if policy_error:
        return policy_error.model_dump(mode="json")

    config = GitHubConfig.from_env()
    if config.mock_tools or not config.token:
        return _mock_commit_files(request).model_dump(mode="json")

    client = GitHubClient(config)
    try:
        repo = client.get_repo(request.repo_name)
        branch = repo.get("default_branch") or "main"
        ref = client.get_ref(request.repo_name, branch)
        parent_sha = ref["object"]["sha"]
        parent_commit = client.get_commit(request.repo_name, parent_sha)
        base_tree_sha = parent_commit["commit"]["tree"]["sha"]

        tree_elements = []
        for file_payload in request.files:
            blob = client.create_blob(request.repo_name, file_payload.content)
            tree_elements.append(
                {
                    "path": file_payload.path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob["sha"],
                }
            )

        tree = client.create_tree(request.repo_name, base_tree_sha, tree_elements)
        commit = client.create_commit(request.repo_name, request.message, tree["sha"], parent_sha)
        commit_sha = commit["sha"]
        client.update_ref(request.repo_name, branch, commit_sha)

        from tools.verifier import verify_commit

        verification = verify_commit(request.repo_name, commit_sha)
        verification_status = verification.get("verification_status", "failed")
        output = {
            "repo_name": request.repo_name,
            "commit_sha": commit_sha,
            "message": request.message,
            "files_changed": len(request.files),
            "changed_files": [file.path for file in request.files],
            "status": "committed",
            "branch": branch,
            "verification": verification.get("output", {}),
        }
        status = "success" if verification_status == "verified" else "failed"
        if status == "failed":
            return ToolResult.failure(
                "github.commit_files",
                verification.get("error") or "Commit was created but verification failed.",
                output,
                verification_status="failed",
            ).model_dump(mode="json")
        return ToolResult.success("github.commit_files", output).model_dump(mode="json")
    except Exception as exc:
        return ToolResult.failure("github.commit_files", str(exc)).model_dump(mode="json")
