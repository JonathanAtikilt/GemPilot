import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from agent.live_adapters import LiveRagMemoryAdapter, LiveToolAdapter, LiveAuditAdapter


@pytest.mark.asyncio
async def test_live_rag_memory_adapter():
    adapter = LiveRagMemoryAdapter()
    with patch("agent.live_adapters.search_rag", new_callable=AsyncMock) as mock_search:
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"id": "mock_chunk"}
        mock_search.return_value = ([mock_result], None)
        
        docs = await adapter.retrieve_hackathon_context("test")
        assert docs == [{"id": "mock_chunk"}]
        mock_search.assert_awaited_with(query="test", top_k=5, doc_types=["hackathon_rules"])

        docs = await adapter.retrieve_nvidia_context("test2")
        assert docs == [{"id": "mock_chunk"}]
        mock_search.assert_awaited_with(query="test2", top_k=5, doc_types=["nvidia_docs"])

        docs = await adapter.find_similar_builds("issue")
        assert docs == [{"id": "mock_chunk"}]
        mock_search.assert_awaited_with(query="issue", top_k=5, doc_types=["build_log"])
        
        await adapter.write_memory({})


def test_live_tool_adapter():
    adapter = LiveToolAdapter()
    
    with patch("agent.live_adapters.create_repo") as mock_create_repo:
        mock_create_repo.return_value = {"status": "success"}
        res = adapter.create_repo("task_12345678", "public")
        assert res == {"status": "success"}
        mock_create_repo.assert_called_with(repo_name="mvpilot-demo-task_123", description="Generated MVP", visibility="public")

    with patch("agent.live_adapters.commit_files") as mock_commit:
        mock_commit.return_value = {"status": "success"}
        res = adapter.commit_files("repo", [{"path": "a.txt", "content": "x"}], "msg")
        assert res == {"status": "success"}

    with patch("agent.live_adapters.check_repo_health") as mock_check:
        mock_check.return_value = {"status": "success"}
        res = adapter.check_repo_health("repo")
        assert res == {"status": "success"}

    with patch("agent.live_adapters.detect_blocker") as mock_detect:
        mock_detect.return_value = {"status": "success"}
        res = adapter.detect_blocker([{}])
        assert res == {"status": "success"}

    with patch("agent.live_adapters.verify_commit") as mock_verify:
        mock_verify.return_value = {"status": "success"}
        res = adapter.verify_commit("repo", "sha")
        assert res == {"status": "success"}
        
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
