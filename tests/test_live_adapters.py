import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from agent.live_adapters import LiveRagMemoryAdapter, LiveToolAdapter, LiveAuditAdapter
from agent.rag.errors import RagConfigurationError


@pytest.mark.asyncio
async def test_live_rag_memory_adapter():
    adapter = LiveRagMemoryAdapter()
    with patch("agent.live_adapters.search_rag", new_callable=AsyncMock) as mock_search, \
         patch("agent.rag.store.get_rag_store") as mock_get_store, \
         patch("agent.rag.embed.embed_text", new_callable=AsyncMock) as mock_embed:
        
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_store.search_memories = AsyncMock(return_value=[{"id": "mock_chunk"}])
        mock_store.write_memory = AsyncMock()
        mock_embed.return_value = [0.1, 0.2]

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"id": "mock_chunk"}
        mock_search.return_value = [mock_result]
        
        docs = await adapter.retrieve_hackathon_context("test")
        assert docs == [{"id": "mock_chunk"}]
        mock_search.assert_awaited_with(query="test", top_k=5, doc_types=["hackathon_rules"])

        docs = await adapter.retrieve_nvidia_context("test2")
        assert docs == [{"id": "mock_chunk"}]
        mock_search.assert_awaited_with(query="test2", top_k=5, doc_types=["nvidia_docs"])

        docs = await adapter.find_similar_builds("issue")
        assert docs == [{"id": "mock_chunk"}]
        mock_store.search_memories.assert_awaited_with([0.1, 0.2], top_k=5)
        
        memory_payload = {"summary": "test summary"}
        await adapter.write_memory(memory_payload)
        mock_embed.assert_awaited_with("test summary", input_type="document")
        mock_store.write_memory.assert_awaited_with({"summary": "test summary", "embedding": [0.1, 0.2]})


@pytest.mark.asyncio
async def test_live_rag_memory_adapter_retrieve_build_context():
    adapter = LiveRagMemoryAdapter()
    with patch(
        "agent.live_adapters.get_build_context",
        new_callable=AsyncMock,
    ) as mock_get_build_context:
        from agent.rag.types import BuildContextItem, BuildContextResponse

        mock_get_build_context.return_value = BuildContextResponse(
            requiredDeliverables=[
                BuildContextItem(
                    item="Working MVP",
                    priority="critical",
                    reason="test",
                    source="rag/sources/mvpilot_build_requirements.md",
                )
            ],
            allowedToolsAndAPIs=[],
            requiredRepositoryFormat=[],
            requiredDemoFormat=[],
            requiredTechStackPieces=[],
            scopeWarnings=[],
            evidence=[],
        )

        payload = await adapter.retrieve_build_context("task-1", "hackathon agent idea")
        assert payload["mode"] == "live"
        assert payload["requiredDeliverables"][0]["item"] == "Working MVP"
        mock_get_build_context.assert_awaited_once()


@pytest.mark.asyncio
async def test_live_rag_memory_adapter_build_context_raises_without_rag_config():
    adapter = LiveRagMemoryAdapter()
    with patch(
        "agent.live_adapters.get_build_context",
        new_callable=AsyncMock,
        side_effect=RagConfigurationError("missing config"),
    ):
        with pytest.raises(RagConfigurationError, match="missing config"):
            await adapter.retrieve_build_context("task-1", "hackathon agent idea")


def test_live_tool_adapter():
    adapter = LiveToolAdapter()
    
    with patch("agent.live_adapters.create_repo") as mock_create_repo:
        mock_create_repo.return_value = {
            "tool_name": "github.create_repo",
            "status": "success",
            "verification_status": "verified",
            "output": {
                "repo_name": "mvpilot-generated-task_123",
                "repo_url": "https://github.com/test/mvpilot-generated-task_123",
                "visibility": "public",
            },
            "error": None,
        }
        res = adapter.create_repo("task_12345678", "public")
        assert res["status"] == "success"
        assert res["tool"] == "github.create_repo"
        assert res["repo"]["name"] == "mvpilot-generated-task_123"
        assert res["repo"]["url"] == "https://github.com/test/mvpilot-generated-task_123"
        assert res["raw_result"]["tool_name"] == "github.create_repo"
        mock_create_repo.assert_called_with(repo_name="mvpilot-generated-task_123", description="Generated MVP", visibility="public")

    with patch("agent.live_adapters.commit_files") as mock_commit:
        mock_commit.return_value = {
            "tool_name": "github.commit_files",
            "status": "success",
            "verification_status": "verified",
            "output": {
                "commit_sha": "abc123",
                "changed_files": ["a.txt"],
            },
            "error": None,
        }
        res = adapter.commit_files("repo", [{"path": "a.txt", "content": "x"}], "msg")
        assert res["status"] == "success"
        assert res["commit_sha"] == "abc123"
        assert res["files"] == ["a.txt"]
        assert res["raw_result"]["tool_name"] == "github.commit_files"

    with patch("agent.live_adapters.check_repo_health") as mock_check:
        mock_check.return_value = {
            "tool_name": "github.check_repo_health",
            "status": "success",
            "verification_status": "verified",
            "output": {"healthy": True, "missing": []},
            "error": None,
        }
        res = adapter.check_repo_health("repo")
        assert res["status"] == "success"
        assert res["healthy"] is True
        assert res["raw_result"]["tool_name"] == "github.check_repo_health"

    with patch("agent.live_adapters.detect_blocker") as mock_detect:
        mock_detect.return_value = {
            "tool_name": "build.detect_blocker",
            "status": "success",
            "verification_status": "not_checked",
            "output": {
                "has_blocker": True,
                "blocker_type": "route_mismatch",
                "summary": "Route mismatch detected.",
                "recommended_fix": "Update frontend route.",
            },
            "error": None,
        }
        res = adapter.detect_blocker([{}])
        assert res["status"] == "success"
        assert res["recoverable"] is True
        assert res["blocker_type"] == "route_mismatch"
        assert res["raw_result"]["tool_name"] == "build.detect_blocker"

    with patch("agent.live_adapters.verify_commit") as mock_verify:
        mock_verify.return_value = {
            "tool_name": "github.verify_commit",
            "status": "success",
            "verification_status": "verified",
            "output": {
                "commit_sha": "sha",
                "files_changed": ["a.txt"],
            },
            "error": None,
        }
        res = adapter.verify_commit("repo", "sha")
        assert res["status"] == "success"
        assert res["verification_status"] == "verified"
        assert res["files_changed"] == ["a.txt"]
        assert res["raw_result"]["tool_name"] == "github.verify_commit"
        
    assert adapter.verify_build(recovered=False)["status"] == "failed"
    assert adapter.verify_build(recovered=True)["status"] == "success"
    assert adapter.recover_build()["status"] == "success"


def test_live_audit_adapter():
    adapter = LiveAuditAdapter(model_name="test-model")
    
    step = adapter.write_audit_log("node", "msg", ["trace"], "status")
    assert step.node_name == "node"
    assert step.message == "msg"
    assert step.model == "test-model"
    assert "Live mode: running live audit trace." in step.decision_trace

    res = adapter.write_tool_call("tool", {}, {})
    assert res["tool_name"] == "tool"

    res = adapter.write_artifact("name", "json", {})
    assert res["name"] == "name"
