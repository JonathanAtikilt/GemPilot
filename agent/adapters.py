import logging
from typing import Any, Protocol
from datetime import UTC, datetime

from agent.schemas import AgentStep

logger = logging.getLogger(__name__)

class RagMemoryAdapter(Protocol):
    async def index_source_urls(self, urls: list[str]) -> dict[str, Any]: ...
    async def retrieve_hackathon_context(self, idea: str) -> list[dict[str, Any]]: ...
    async def retrieve_provider_context(self, idea: str) -> list[dict[str, Any]]: ...
    async def find_similar_builds(self, issue: str) -> list[dict[str, Any]]: ...
    async def retrieve_build_context(
        self,
        project_id: str,
        idea: str,
        *,
        optional_params: dict[str, Any] | None = None,
        rules_url: str | None = None,
        reference_urls: list[str] | None = None,
        context_needed: list[str] | None = None,
        top_k: int = 8,
    ) -> dict[str, Any]: ...
    async def write_memory(self, memory: dict[str, Any]) -> None: ...

class ToolAdapter(Protocol):
    def create_repo(
        self,
        task_id: str,
        visibility: str,
        *,
        repo_preference: str = "create_new_repo",
        repo_name: str | None = None,
        repo_description: str | None = None,
        repo_url: str | None = None,
    ) -> dict[str, Any]: ...
    def commit_files(self, repo_name: str, files: list[dict[str, Any]], message: str) -> dict[str, Any]: ...
    def check_repo_health(self, repo_name: str) -> dict[str, Any]: ...
    def detect_blocker(self, logs: list[dict[str, Any]]) -> dict[str, Any]: ...
    def verify_commit(self, repo_name: str, commit_sha: str) -> dict[str, Any]: ...
    def verify_build(self, recovered: bool, repo_name: str | None = None) -> dict[str, Any]: ...
    def recover_build(self) -> dict[str, Any]: ...

class AuditAdapter(Protocol):
    def write_audit_log(
        self,
        node_name: str,
        message: str,
        decision_trace: list[str],
        status: str,
        *,
        project_id: str | None = None,
        flight_stage: str | None = None,
        agent: str | None = None,
    ) -> AgentStep: ...


class InMemoryRagMemoryAdapter:
    """Mock-safe retrieval adapter using local build-context helpers."""

    async def index_source_urls(self, urls: list[str]) -> dict[str, Any]:
        return {"documentsLoaded": 0, "chunksCreated": 0, "skippedUrls": list(urls)}

    async def retrieve_hackathon_context(self, idea: str) -> list[dict[str, Any]]:
        return await _search_context(idea, ["hackathon_rules"])

    async def retrieve_provider_context(self, idea: str) -> list[dict[str, Any]]:
        return await _search_context(idea, ["ai_provider_docs", "llm_model_docs", "llm_model_usage"])

    async def retrieve_build_context(
        self,
        project_id: str,
        idea: str,
        *,
        optional_params: dict[str, Any] | None = None,
        rules_url: str | None = None,
        reference_urls: list[str] | None = None,
        context_needed: list[str] | None = None,
        top_k: int = 8,
    ) -> dict[str, Any]:
        del rules_url, reference_urls, context_needed
        from agent.rag.build_context import get_build_context

        try:
            response = await get_build_context(project_id, idea, optional_params, top_k=top_k)
            payload = response.model_dump(mode="json", by_alias=True)
            payload.setdefault("mode", "live")
            return payload
        except Exception:
            logger.warning("retrieve_build_context failed for project %s; using fallback", project_id, exc_info=True)
            return _fallback_build_context()

    async def find_similar_builds(self, issue: str) -> list[dict[str, Any]]:
        try:
            from agent.rag.store import get_rag_store

            return await get_rag_store().search_memories(issue)
        except Exception:
            logger.warning("find_similar_builds failed for issue %r; returning empty list", issue, exc_info=True)
            return []

    async def write_memory(self, memory: dict[str, Any]) -> None:
        try:
            from agent.rag.store import get_rag_store

            await get_rag_store().write_memory(memory)
        except Exception:
            logger.warning("write_memory failed; memory entry was not persisted", exc_info=True)
            return None


async def _search_context(idea: str, doc_types: list[str]) -> list[dict[str, Any]]:
    try:
        from agent.rag import build_context

        chunks = await build_context.search_rag(idea, top_k=4, doc_types=doc_types)
    except Exception:
        logger.debug("_search_context RAG search failed for doc_types %s; returning empty", doc_types, exc_info=True)
        return []
    return [
        {
            "source": chunk.source,
            "title": chunk.title,
            "doc_type": chunk.doc_type,
            "text": chunk.text,
            "score": chunk.score,
        }
        for chunk in chunks
    ]


def _fallback_build_context() -> dict[str, Any]:
    return {
        "mode": "mock",
        "requiredDeliverables": [
            {
                "item": "Complete hackathon-ready full-stack project",
                "priority": "high",
                "reason": "Mock fallback build context.",
                "source": "in_memory_mock_context",
            }
        ],
        "allowedToolsAndAPIs": [],
        "requiredRepositoryFormat": [
            {
                "item": "README, docs, demo materials, source, tests, seed data, and .env.example",
                "priority": "high",
                "reason": "Mock fallback build context.",
                "source": "in_memory_mock_context",
            }
        ],
        "requiredDemoFormat": [
            {
                "item": "demo/script.md, demo/storyboard.md, demo/demo_walkthrough.md, and demo/video_outline.md",
                "priority": "high",
                "reason": "Mock fallback build context.",
                "source": "in_memory_mock_context",
            }
        ],
        "requiredTechStackPieces": [],
        "agentBoundaries": [],
        "resolvedTechStack": {
            "source": "default",
            "requiredItems": [],
            "defaultItems": ["React", "FastAPI", "Postgres", "pytest", "npm run build"],
            "items": ["React", "FastAPI", "Postgres", "pytest", "npm run build"],
        },
        "scopeWarnings": [],
        "evidence": [],
    }


class InMemoryToolAdapter:
    def create_repo(
        self,
        task_id: str,
        visibility: str,
        *,
        repo_preference: str = "create_new_repo",
        repo_name: str | None = None,
        repo_description: str | None = None,
        repo_url: str | None = None,
    ) -> dict[str, Any]:
        del repo_description
        repo_name = repo_name or f"gempilot-{task_id[:8]}"
        return {
            "tool": "github.create_repo" if repo_preference == "create_new_repo" else "github.use_existing_repo",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "repo": {
                "name": repo_name,
                "visibility": visibility,
                "url": repo_url or f"https://github.com/mock-org/{repo_name}",
            },
            "summary": (
                "Test mode: created deterministic GitHub repository record."
                if repo_preference == "create_new_repo"
                else "Test mode: attached deterministic existing GitHub repository record."
            ),
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
            "commit_url": f"https://github.com/mock-org/{repo_name}/commit/mock-commit-0001",
            "summary": "Test mode: committed generated full-stack project package files.",
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
            "summary": "Test mode: missing idea-specific generated artifact.",
            "recommended_fix": "Add deterministic idea-specific artifact stub."
        }

    def verify_commit(self, repo_name: str, commit_sha: str) -> dict[str, Any]:
        return {
            "tool": "github.verify_commit",
            "status": "success",
            "mock_mode": True,
            "verification_status": "verified"
        }

    def verify_build(self, recovered: bool, repo_name: str | None = None) -> dict[str, Any]:
        if not recovered:
            return {
                "tool": "build.verify",
                "status": "failed",
                "mock_mode": True,
                "recoverable": True,
                "error": "Test mode: missing idea-specific generated artifact.",
                "summary": "Test mode: build failed with a recoverable artifact gap.",
            }
        return {
            "tool": "build.verify",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "checks": ["unit", "lint", "package"],
            "summary": "Test mode: build verification passed after recovery.",
        }

    def recover_build(self) -> dict[str, Any]:
        return {
            "tool": "build.apply_recovery_patch",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "patch": "Add deterministic idea-specific artifact stub.",
            "summary": "Test mode: applied recovery patch for the blocked build.",
        }


class InMemoryAuditAdapter:
    def __init__(self, model_name: str = "mock-model"):
        self._model_name = model_name

    def write_audit_log(
        self,
        node_name: str,
        message: str,
        decision_trace: list[str],
        status: str = "completed",
        *,
        project_id: str | None = None,
        flight_stage: str | None = None,
        agent: str | None = None,
    ) -> AgentStep:
        return AgentStep(
            project_id=project_id,
            flight_stage=flight_stage,
            agent=agent,
            node_name=node_name,
            status=status,
            message=message,
            model=self._model_name,
            decision_trace=[
                "Mock mode: deterministic provider-backed reasoning.",
                *decision_trace,
            ],
            timestamp=datetime.now(UTC),
        )
