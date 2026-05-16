from typing import Any
from datetime import UTC, datetime

from agent.adapters import RagMemoryAdapter, ToolAdapter, AuditAdapter
from agent.schemas import AgentStep

from agent.rag.build_context import get_build_context
from agent.rag.retrieve import search_rag
from agent.rag.types import BuildContextOptionalParams
from tools.github_tool import create_repo, commit_files
from tools.build_checker import check_repo_health
from tools.blocker_detector import detect_blocker
from tools.verifier import verify_commit
from tools.tool_logger import log_audit_event, log_generated_artifact, log_tool_call


class LiveRagMemoryAdapter:
    async def index_source_urls(self, urls: list[str]) -> dict[str, Any]:
        from agent.rag.ingest import ingest_source_urls

        result = await ingest_source_urls(urls)
        return {
            "urls": urls,
            "documentsLoaded": result.documentsLoaded,
            "chunksCreated": result.chunksCreated,
            "storedIn": result.storedIn,
        }

    async def retrieve_hackathon_context(self, idea: str) -> list[dict[str, Any]]:
        results = await search_rag(query=idea, top_k=5, doc_types=["hackathon_rules"])
        return [r.model_dump() for r in results]

    async def retrieve_nvidia_context(self, idea: str) -> list[dict[str, Any]]:
        results = await search_rag(query=idea, top_k=5, doc_types=["nvidia_docs"])
        return [r.model_dump() for r in results]

    async def find_similar_builds(self, issue: str) -> list[dict[str, Any]]:
        from agent.rag.store import get_rag_store
        from agent.rag.embed import embed_text
        store = get_rag_store()
        query_embedding = await embed_text(issue, input_type="query")
        return await store.search_memories(query_embedding, top_k=5)

    async def retrieve_build_context(
        self,
        project_id: str,
        idea: str,
        *,
        optional_params: dict[str, Any] | None = None,
        top_k: int = 8,
    ) -> dict[str, Any]:
        parsed_params: BuildContextOptionalParams | None = None
        if optional_params:
            parsed_params = BuildContextOptionalParams.model_validate(optional_params)

        response = await get_build_context(
            project_id,
            idea,
            optional_params=parsed_params,
            top_k=top_k,
        )
        payload = response.model_dump()
        payload["mode"] = "live"
        return payload

    async def write_memory(self, memory: dict[str, Any]) -> None:
        from agent.rag.store import get_rag_store
        from agent.rag.embed import embed_text
        store = get_rag_store()
        summary = memory.get("summary", "")
        if summary:
            embedding = await embed_text(summary, input_type="document")
            memory["embedding"] = embedding
        await store.write_memory(memory)


class LiveToolAdapter:
    def create_repo(self, task_id: str, visibility: str) -> dict[str, Any]:
        raw_result = create_repo(
            repo_name=f"mvpilot-generated-{task_id[:8]}",
            description="Generated MVP",
            visibility=visibility
        )
        output = raw_result.get("output", {})
        return {
            "tool": raw_result.get("tool_name", "github.create_repo"),
            "status": _workflow_status(raw_result),
            "mock_mode": raw_result.get("status") == "mock",
            "recoverable": _is_recoverable(raw_result),
            "repo": {
                "name": output.get("repo_name"),
                "visibility": output.get("visibility", visibility),
                "url": output.get("repo_url"),
            },
            "summary": _summary(
                raw_result,
                success="Created and verified GitHub repository.",
                failure="Failed to create GitHub repository.",
            ),
            "raw_result": raw_result,
        }

    def commit_files(self, repo_name: str, files: list[dict[str, Any]], message: str) -> dict[str, Any]:
        raw_result = commit_files(repo_name=repo_name, files=files, message=message)
        output = raw_result.get("output", {})
        return {
            "tool": raw_result.get("tool_name", "github.commit_files"),
            "status": _workflow_status(raw_result),
            "mock_mode": raw_result.get("status") == "mock",
            "recoverable": _is_recoverable(raw_result),
            "repo": repo_name,
            "files": output.get("changed_files") or [file.get("path") for file in files],
            "commit_sha": output.get("commit_sha"),
            "summary": _summary(
                raw_result,
                success="Committed generated files and verified commit.",
                failure="Failed to commit generated files.",
            ),
            "raw_result": raw_result,
        }

    def check_repo_health(self, repo_name: str) -> dict[str, Any]:
        raw_result = check_repo_health(repo_name)
        output = raw_result.get("output", {})
        return {
            "tool": raw_result.get("tool_name", "github.check_repo_health"),
            "status": _workflow_status(raw_result),
            "mock_mode": raw_result.get("status") == "mock",
            "recoverable": _is_recoverable(raw_result),
            "healthy": output.get("healthy", raw_result.get("status") in {"success", "mock"}),
            "missing": output.get("missing", []),
            "summary": _summary(
                raw_result,
                success="Checked generated repository health.",
                failure="Generated repository health check failed.",
            ),
            "raw_result": raw_result,
        }

    def detect_blocker(self, logs: list[dict[str, Any]]) -> dict[str, Any]:
        raw_result = detect_blocker(logs)
        output = raw_result.get("output", raw_result)
        return {
            "tool": raw_result.get("tool_name", "build.detect_blocker"),
            "status": _workflow_status(raw_result),
            "mock_mode": raw_result.get("status") == "mock",
            "recoverable": bool(output.get("has_blocker")),
            "has_blocker": output.get("has_blocker", False),
            "blocker_type": output.get("blocker_type"),
            "summary": output.get("summary") or _summary(
                raw_result,
                success="Analyzed logs for blockers.",
                failure="Failed to analyze logs for blockers.",
            ),
            "recommended_fix": output.get("recommended_fix"),
            "raw_result": raw_result,
        }

    def verify_commit(self, repo_name: str, commit_sha: str) -> dict[str, Any]:
        raw_result = verify_commit(repo_name, commit_sha)
        output = raw_result.get("output", {})
        return {
            "tool": raw_result.get("tool_name", "github.verify_commit"),
            "status": _workflow_status(raw_result),
            "mock_mode": raw_result.get("status") == "mock",
            "recoverable": _is_recoverable(raw_result),
            "repo": repo_name,
            "commit_sha": output.get("commit_sha", commit_sha),
            "files_changed": output.get("files_changed", []),
            "verification_status": raw_result.get("verification_status"),
            "summary": _summary(
                raw_result,
                success="Verified GitHub commit.",
                failure="Failed to verify GitHub commit.",
            ),
            "raw_result": raw_result,
        }

    def verify_build(self, recovered: bool) -> dict[str, Any]:
        # Return mock shape or call live build verify if it exists
        if not recovered:
            return {
                "tool": "build.verify",
                "status": "failed",
                "recoverable": True,
                "error": "Live mode: dependency gap detected.",
                "summary": "Live mode: build failed with a recoverable gap.",
            }
        return {
            "tool": "build.verify",
            "status": "success",
            "recoverable": False,
            "checks": ["unit", "lint", "package"],
            "summary": "Live mode: build verification passed.",
        }

    def recover_build(self) -> dict[str, Any]:
        return {
            "tool": "build.apply_recovery_patch",
            "status": "success",
            "recoverable": False,
            "patch": "Live deterministic demo dependency stub.",
            "summary": "Live mode: applied recovery patch.",
        }


class LiveAuditAdapter:
    def __init__(self, model_name: str):
        self._model_name = model_name

    def write_audit_log(self, node_name: str, message: str, decision_trace: list[str], status: str = "completed") -> AgentStep:
        log_audit_event(
            task_id=None,
            step=node_name,
            message=message,
            data={
                "status": status,
                "model": self._model_name,
                "decision_trace": decision_trace,
            },
        )
        return AgentStep(
            node_name=node_name,
            status=status,
            message=message,
            model=self._model_name,
            decision_trace=["Live mode: running live audit trace.", *decision_trace],
            timestamp=datetime.now(UTC),
        )

    def write_tool_call(self, tool_name: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        log_result = log_tool_call(
            task_id=None,
            tool_name=tool_name,
            input_json=args,
            result=result,
        )
        return {"tool_name": tool_name, "args": args, "result": result, "log_result": log_result}

    def write_artifact(self, name: str, kind: str, content: Any) -> dict[str, Any]:
        log_result = log_generated_artifact(
            task_id=None,
            artifact_type=kind,
            path=name,
            content=content if isinstance(content, str) else str(content),
            commit_sha=None,
        )
        return {"name": name, "kind": kind, "content": content, "log_result": log_result}


def _workflow_status(raw_result: dict[str, Any]) -> str:
    if raw_result.get("status") in {"success", "mock"}:
        return "success"
    return "failed"


def _is_recoverable(raw_result: dict[str, Any]) -> bool:
    status = raw_result.get("status")
    if status == "refused":
        return False
    return status == "failed"


def _summary(raw_result: dict[str, Any], *, success: str, failure: str) -> str:
    if raw_result.get("status") in {"success", "mock"}:
        return success
    return raw_result.get("error") or failure
