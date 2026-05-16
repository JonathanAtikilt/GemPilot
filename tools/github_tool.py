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

from tools.http_ssl import default_ssl_context
from tools.policy import repo_prefix, validate_action, validate_file_payloads, validate_github_mutation
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
            with urlopen(request, timeout=20, context=default_ssl_context()) as response:
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
        tree_elements: list[dict[str, Any]],
        *,
        base_tree_sha: str | None = None,
    ) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        payload: dict[str, Any] = {"tree": tree_elements}
        if base_tree_sha:
            payload["base_tree"] = base_tree_sha
        return self.request(
            "POST",
            f"/repos/{self.config.owner}/{repo_name}/git/trees",
            payload,
        )

    def create_commit(
        self,
        repo_name: str,
        message: str,
        tree_sha: str,
        *,
        parent_sha: str | None = None,
    ) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        parents = [parent_sha] if parent_sha else []
        return self.request(
            "POST",
            f"/repos/{self.config.owner}/{repo_name}/git/commits",
            {"message": message, "tree": tree_sha, "parents": parents},
        )

    def create_ref(self, repo_name: str, branch: str, commit_sha: str) -> dict[str, Any]:
        if not self.config.owner:
            raise RuntimeError("GITHUB_OWNER is required for live GitHub mode.")
        return self.request(
            "POST",
            f"/repos/{self.config.owner}/{repo_name}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": commit_sha},
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
    owner = os.getenv("GITHUB_OWNER", "mock-owner")
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
            "commit_url": f"https://github.com/{owner}/{request.repo_name}/commit/{commit.sha}",
            "message": request.message,
            "files_changed": len(request.files),
            "changed_files": commit.files_changed,
            "status": "committed",
        },
    )


def check_github_auth(config: GitHubConfig | None = None) -> dict:
    """Read-only preflight check for live GitHub configuration."""

    active_config = config or GitHubConfig.from_env()
    if active_config.mock_tools:
        return ToolResult.mock(
            "github.check_auth",
            {
                "authenticated": False,
                "owner": active_config.owner,
                "repo_prefix": active_config.repo_prefix,
                "message": "Mock mode is enabled; live GitHub auth was not checked.",
            },
        ).model_dump(mode="json")
    if not active_config.token:
        return ToolResult.failure(
            "github.check_auth",
            "GITHUB_TOKEN is required for live GitHub mode.",
            {"authenticated": False, "owner": active_config.owner, "repo_prefix": active_config.repo_prefix},
        ).model_dump(mode="json")
    if not active_config.owner:
        return ToolResult.failure(
            "github.check_auth",
            "GITHUB_OWNER is required for live GitHub mode.",
            {"authenticated": False, "repo_prefix": active_config.repo_prefix},
        ).model_dump(mode="json")

    client = GitHubClient(active_config)
    try:
        user = client.get_authenticated_user()
    except Exception as exc:
        return ToolResult.failure(
            "github.check_auth",
            str(exc),
            {"authenticated": False, "owner": active_config.owner, "repo_prefix": active_config.repo_prefix},
        ).model_dump(mode="json")

    login = user.get("login")
    return ToolResult.success(
        "github.check_auth",
        {
            "authenticated": True,
            "login": login,
            "owner": active_config.owner,
            "owner_matches_login": login == active_config.owner,
            "repo_prefix": active_config.repo_prefix,
        },
        verification_status="verified",
    ).model_dump(mode="json")


def create_repo(
    repo_name: str,
    description: str,
    visibility: str,
    *,
    config: GitHubConfig | None = None,
) -> dict:
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

    active_config = config or GitHubConfig.from_env()
    if active_config.mock_tools or not active_config.token:
        return _mock_create_repo(request.repo_name, request.visibility).model_dump(mode="json")

    client = GitHubClient(active_config)
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


def _is_empty_repository_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "409" in message and "empty" in message


def _tree_elements_from_files(client: GitHubClient, repo_name: str, files: list) -> list[dict[str, Any]]:
    tree_elements: list[dict[str, Any]] = []
    for file_payload in files:
        blob = client.create_blob(repo_name, file_payload.content)
        tree_elements.append(
            {
                "path": file_payload.path,
                "mode": "100644",
                "type": "blob",
                "sha": blob["sha"],
            }
        )
    return tree_elements


def _finalize_commit_result(
    *,
    request: CommitFilesRequest,
    active_config: GitHubConfig,
    commit_sha: str,
    branch: str,
) -> dict:
    from tools.verifier import verify_commit

    verification = verify_commit(request.repo_name, commit_sha, config=active_config)
    verification_status = verification.get("verification_status", "failed")
    output = {
        "repo_name": request.repo_name,
        "commit_sha": commit_sha,
        "commit_url": (
            f"https://github.com/{active_config.owner}/{request.repo_name}/commit/{commit_sha}"
            if active_config.owner
            else None
        ),
        "message": request.message,
        "files_changed": len(request.files),
        "changed_files": [file.path for file in request.files],
        "status": "committed",
        "branch": branch,
        "verification": verification.get("output", {}),
    }
    if verification_status != "verified":
        return ToolResult.failure(
            "github.commit_files",
            verification.get("error") or "Commit was created but verification failed.",
            output,
            verification_status="failed",
        ).model_dump(mode="json")
    return ToolResult.success("github.commit_files", output).model_dump(mode="json")


def _commit_files_to_empty_repository(
    client: GitHubClient,
    request: CommitFilesRequest,
    *,
    branch: str,
    config: GitHubConfig,
) -> dict:
    tree_elements = _tree_elements_from_files(client, request.repo_name, request.files)
    tree = client.create_tree(request.repo_name, tree_elements)
    commit = client.create_commit(request.repo_name, request.message, tree["sha"])
    commit_sha = commit["sha"]
    client.create_ref(request.repo_name, branch, commit_sha)
    return _finalize_commit_result(
        request=request,
        active_config=config,
        commit_sha=commit_sha,
        branch=branch,
    )


def commit_files(
    repo_name: str,
    files: list[dict],
    message: str,
    *,
    config: GitHubConfig | None = None,
    allow_existing_repo: bool = False,
) -> dict:
    """Commit multiple text files to a generated repository in one Git commit."""

    try:
        request = CommitFilesRequest(repo_name=repo_name, files=files, message=message)
    except ValidationError as exc:
        return ToolResult.failure(
            "github.commit_files",
            "Commit files request failed validation.",
            {"validation_error": safe_validation_errors(exc.errors(include_url=False))},
        ).model_dump(mode="json")

    if allow_existing_repo:
        policy_error = validate_action("commit_files") or validate_file_payloads(request.files)
    else:
        policy_error = validate_github_mutation("commit_files", request.repo_name, request.files)
    if policy_error:
        return policy_error.model_dump(mode="json")

    active_config = config or GitHubConfig.from_env()
    if active_config.mock_tools or not active_config.token:
        return _mock_commit_files(request).model_dump(mode="json")

    client = GitHubClient(active_config)
    try:
        repo = client.get_repo(request.repo_name)
        branch = repo.get("default_branch") or "main"
        if repo.get("size", 1) == 0:
            return _commit_files_to_empty_repository(
                client,
                request,
                branch=branch,
                config=active_config,
            )

        try:
            ref = client.get_ref(request.repo_name, branch)
        except RuntimeError as exc:
            if _is_empty_repository_error(exc):
                return _commit_files_to_empty_repository(
                    client,
                    request,
                    branch=branch,
                    config=active_config,
                )
            raise

        parent_sha = ref["object"]["sha"]
        parent_commit = client.get_commit(request.repo_name, parent_sha)
        base_tree_sha = parent_commit["commit"]["tree"]["sha"]
        tree_elements = _tree_elements_from_files(client, request.repo_name, request.files)
        tree = client.create_tree(request.repo_name, tree_elements, base_tree_sha=base_tree_sha)
        commit = client.create_commit(
            request.repo_name,
            request.message,
            tree["sha"],
            parent_sha=parent_sha,
        )
        commit_sha = commit["sha"]
        client.update_ref(request.repo_name, branch, commit_sha)
        return _finalize_commit_result(
            request=request,
            active_config=active_config,
            commit_sha=commit_sha,
            branch=branch,
        )
    except Exception as exc:
        return ToolResult.failure("github.commit_files", str(exc)).model_dump(mode="json")
