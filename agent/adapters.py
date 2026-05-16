from typing import Any, Protocol
from datetime import UTC, datetime

from agent.schemas import AgentStep

class RagMemoryAdapter(Protocol):
    async def retrieve_hackathon_context(self, idea: str) -> list[dict[str, Any]]: ...
    async def retrieve_nvidia_context(self, idea: str) -> list[dict[str, Any]]: ...
    async def find_similar_builds(self, issue: str) -> list[dict[str, Any]]: ...
    async def write_memory(self, memory: dict[str, Any]) -> None: ...

class ToolAdapter(Protocol):
    def create_repo(self, task_id: str, visibility: str) -> dict[str, Any]: ...
    def commit_files(self, repo_name: str, files: list[dict[str, Any]], message: str) -> dict[str, Any]: ...
    def check_repo_health(self, repo_name: str) -> dict[str, Any]: ...
    def detect_blocker(self, logs: list[dict[str, Any]]) -> dict[str, Any]: ...
    def verify_commit(self, repo_name: str, commit_sha: str) -> dict[str, Any]: ...
    def verify_build(self, recovered: bool) -> dict[str, Any]: ...
    def recover_build(self) -> dict[str, Any]: ...

class AuditAdapter(Protocol):
    def write_audit_log(
        self, node_name: str, message: str, decision_trace: list[str], status: str
    ) -> AgentStep: ...


class InMemoryRagMemoryAdapter:
    async def retrieve_hackathon_context(self, idea: str) -> list[dict[str, Any]]:
        return [{
            "source": "hackathon_brief",
            "title": "MVPilot healthcare demo lane",
            "snippet": (
                "Mock mode: prioritize a visible referral workflow, judge-ready "
                "README, and short pitch package."
            ),
            "query": idea,
            "score": 0.94,
        }]

    async def retrieve_nvidia_context(self, idea: str) -> list[dict[str, Any]]:
        return [{
            "source": "nvidia_reference",
            "title": "Nemotron reasoning pattern",
            "snippet": (
                "Mock mode: every agent step should expose model name and a "
                "compact decision trace."
            ),
            "score": 0.91,
        }]

    async def find_similar_builds(self, issue: str) -> list[dict[str, Any]]:
        return [{
            "source": "previous_demo",
            "summary": (
                "Mock mode: healthcare referral demos land better when blockers "
                "show recovery instead of a perfect run."
            ),
            "score": 0.88,
        },
        {
            "source": "team_split",
            "summary": (
                "Mock mode: Person 1 owns orchestration and produces artifacts "
                "for downstream UI/demo surfaces."
            ),
            "score": 0.84,
        }]

    async def write_memory(self, memory: dict[str, Any]) -> None:
        pass


class InMemoryToolAdapter:
    def create_repo(self, task_id: str, visibility: str) -> dict[str, Any]:
        repo_name = f"mvpilot-demo-{task_id[:8]}"
        return {
            "tool": "github.create_repo",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "repo": {
                "name": repo_name,
                "visibility": visibility,
                "url": f"https://github.com/mock-org/{repo_name}",
            },
            "summary": "Mock mode: created deterministic GitHub repository record.",
        }

    def commit_files(self, repo_name: str, files: list[dict[str, Any]], message: str) -> dict[str, Any]:
        return {
            "tool": "github.commit_files",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "repo": repo_name,
            "files": files,
            "commit_sha": "mock-commit-0001",
            "summary": "Mock mode: committed generated MVP package files.",
        }

    def check_repo_health(self, repo_name: str) -> dict[str, Any]:
        return {
            "tool": "build.check_repo_health",
            "status": "success",
            "mock_mode": True,
            "healthy": True,
        }

    def detect_blocker(self, logs: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "has_blocker": True,
            "blocker_type": "missing_dependency",
            "summary": "Mock mode: missing demo dependency in generated package.",
            "recommended_fix": "Add deterministic demo dependency stub."
        }

    def verify_commit(self, repo_name: str, commit_sha: str) -> dict[str, Any]:
        return {
            "tool": "github.verify_commit",
            "status": "success",
            "mock_mode": True,
            "verification_status": "verified"
        }

    def verify_build(self, recovered: bool) -> dict[str, Any]:
        if not recovered:
            return {
                "tool": "build.verify",
                "status": "failed",
                "mock_mode": True,
                "recoverable": True,
                "error": "Mock mode: missing demo dependency in generated package.",
                "summary": "Mock mode: build failed with a recoverable dependency gap.",
            }
        return {
            "tool": "build.verify",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "checks": ["unit", "lint", "package"],
            "summary": "Mock mode: build verification passed after recovery.",
        }

    def recover_build(self) -> dict[str, Any]:
        return {
            "tool": "build.apply_recovery_patch",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "patch": "Add deterministic demo dependency stub.",
            "summary": "Mock mode: applied recovery patch for the blocked build.",
        }


class InMemoryAuditAdapter:
    def __init__(self, model_name: str = "mock-model"):
        self._model_name = model_name

    def write_audit_log(self, node_name: str, message: str, decision_trace: list[str], status: str = "completed") -> AgentStep:
        return AgentStep(
            node_name=node_name,
            status=status,
            message=message,
            model=self._model_name,
            decision_trace=[
                "Mock mode: deterministic Nemotron-style reasoning.",
                *decision_trace,
            ],
            timestamp=datetime.now(UTC),
        )
