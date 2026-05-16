"""In-memory mock backend for demo-safe tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MockCommit:
    sha: str
    message: str
    files_changed: list[str]


@dataclass
class MockRepo:
    repo_name: str
    files: dict[str, str] = field(default_factory=dict)
    commits: list[MockCommit] = field(default_factory=list)


_REPOS: dict[str, MockRepo] = {}


def reset_mock_store() -> None:
    _REPOS.clear()


def ensure_repo(repo_name: str) -> MockRepo:
    if repo_name not in _REPOS:
        _REPOS[repo_name] = MockRepo(repo_name=repo_name)
    return _REPOS[repo_name]


def create_repo(repo_name: str) -> MockRepo:
    return ensure_repo(repo_name)


def commit_files(repo_name: str, files: dict[str, str], message: str) -> MockCommit:
    repo = ensure_repo(repo_name)
    repo.files.update(files)
    sha = f"mock-{len(repo.commits) + 1:07d}"
    commit = MockCommit(sha=sha, message=message, files_changed=list(files.keys()))
    repo.commits.append(commit)
    return commit


def get_file(repo_name: str, path: str) -> str | None:
    repo = ensure_repo(repo_name)
    return repo.files.get(path)


def list_files(repo_name: str) -> set[str]:
    repo = ensure_repo(repo_name)
    return set(repo.files)


def get_commit(repo_name: str, commit_sha: str) -> MockCommit | None:
    repo = ensure_repo(repo_name)
    return next((commit for commit in repo.commits if commit.sha == commit_sha), None)


def commit_count(repo_name: str) -> int:
    repo = ensure_repo(repo_name)
    return len(repo.commits)
