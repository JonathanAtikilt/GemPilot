import pytest

from agent.config import Settings
from agent.model_client import DeterministicModelClient
from agent.rag.build_context import get_build_context
from agent.schemas import RunAgentRequest, TaskStatus
from agent.service import AgentService
from agent.task_store import InMemoryTaskStore
from agent.adapters import InMemoryToolAdapter
from agent.workflow import (
    build_initial_state,
    build_workflow,
    route_after_tool_result,
)


VALID_IDEA = (
    "Build a healthcare referral coordination agent that helps clinics "
    "prevent failed referrals."
)


class CapturingModelClient(DeterministicModelClient):
    def __init__(self) -> None:
        super().__init__(mode="mock")
        self.prompts: dict[str, str] = {}

    async def complete_structured(self, **kwargs):
        self.prompts[kwargs["purpose"]] = kwargs["prompt"]
        return await super().complete_structured(**kwargs)


class EmptyRagAdapter:
    async def retrieve_build_context(
        self,
        project_id: str,
        idea: str,
        *,
        optional_params: dict | None = None,
        top_k: int = 8,
    ) -> dict:
        response = await get_build_context(
            project_id,
            idea,
            optional_params=optional_params,
            top_k=top_k,
        )
        payload = response.model_dump()
        payload["mode"] = "live"
        return payload

    async def retrieve_hackathon_context(self, idea: str) -> list[dict]:
        return []

    async def retrieve_nvidia_context(self, idea: str) -> list[dict]:
        return []

    async def find_similar_builds(self, issue: str) -> list[dict]:
        return []

    async def write_memory(self, memory: dict) -> None:
        return None


@pytest.mark.asyncio
async def test_full_workflow_completes_with_expected_timeline(mock_live_rag_search):
    settings = Settings(_env_file=None, adapter_mode="mock")
    task_store = InMemoryTaskStore()
    service = AgentService(task_store, settings)
    response = await service.start_task(
        RunAgentRequest(
            idea=VALID_IDEA,
            repo_visibility="public",
            demo_mode=True,
        )
    )

    await service.run_task_workflow(response.task_id)

    detail = await task_store.get_task(response.task_id)
    node_names = [step.node_name for step in detail.graph_trace]

    assert detail.task.status == TaskStatus.COMPLETED
    assert node_names == [
        "receive_idea",
        "retrieve_context",
        "scope_mvp",
        "plan_repo",
        "create_repo",
        "generate_files",
        "commit_progress",
        "verify_build",
        "handle_blocker",
        "verify_build",
        "generate_final_package",
        "remember_outcome",
        "report_result",
    ]
    assert detail.retrieved_docs
    assert detail.build_context
    assert detail.build_context.get("requiredDeliverables")
    assert detail.build_context.get("allowedToolsAndAPIs")
    assert detail.build_context.get("requiredRepositoryFormat")
    assert detail.build_context.get("requiredDemoFormat")
    assert detail.build_context.get("requiredTechStackPieces")
    assert detail.build_context.get("mode") == "live"
    assert detail.build_context.get("evidence")
    assert detail.memory_matches
    assert detail.final_report is not None
    assert detail.final_report["mode"] == "mock"
    assert {artifact["name"] for artifact in detail.generated_artifacts} >= {
        "README.md",
        "demo_script.md",
        "pitch.md",
        "final_report.json",
    }
    model_backed_steps = {
        step.node_name: step
        for step in detail.agent_steps
        if step.prompt_purpose is not None
    }
    assert set(model_backed_steps) == {
        "scope_mvp",
        "plan_repo",
        "generate_files",
        "handle_blocker",
        "generate_final_package",
    }
    assert model_backed_steps["scope_mvp"].model == settings.nemotron_model
    assert model_backed_steps["plan_repo"].model == settings.nemotron_model
    assert model_backed_steps["generate_files"].model == settings.nemotron_fast_model
    assert all(step.model_mode == "mock" for step in model_backed_steps.values())
    assert all(step.decision_trace for step in detail.agent_steps)
    assert detail.final_report["readme"]["content"]
    assert detail.final_report["demo_script"]["content"]
    assert detail.final_report["pitch"]["content"]
    assert detail.final_report["blocker_analysis"]["recoverable"] is True


def test_route_after_tool_result_continues_after_success():
    route = route_after_tool_result(
        {"last_tool_result": {"status": "success", "recoverable": False}}
    )

    assert route == "generate_final_package"


def test_route_after_tool_result_handles_recoverable_blocker():
    route = route_after_tool_result(
        {"last_tool_result": {"status": "failed", "recoverable": True}}
    )

    assert route == "handle_blocker"


def test_route_after_tool_result_fails_unrecoverable_result():
    route = route_after_tool_result(
        {"last_tool_result": {"status": "failed", "recoverable": False}}
    )

    assert route == "failed"


@pytest.mark.asyncio
async def test_workflow_plan_repo_prompt_uses_default_stack_when_rag_stack_is_empty(monkeypatch):
    async def fake_search(query: str, top_k: int = 5, doc_types=None):
        return []

    monkeypatch.setattr("agent.rag.build_context.search_rag", fake_search)

    settings = Settings(_env_file=None, adapter_mode="mock")
    model_client = CapturingModelClient()
    workflow = build_workflow(
        settings,
        model_client=model_client,
        retrieval=EmptyRagAdapter(),
        tools=InMemoryToolAdapter(),
    )
    initial_state = build_initial_state(
        task_id="task-default-stack",
        idea=VALID_IDEA,
        repo_visibility="public",
        demo_mode=True,
        settings=settings,
    )

    final_state = await workflow.ainvoke(initial_state)
    plan_prompt = model_client.prompts["plan_repo"]

    assert final_state["build_context"]["requiredTechStackPieces"] == []
    assert final_state["build_context"]["resolvedTechStack"]["source"] == "default"
    assert "Next.js" in plan_prompt
    assert "FastAPI" in plan_prompt
    assert "Supabase Postgres" in plan_prompt


@pytest.mark.asyncio
async def test_unrecoverable_tool_result_marks_workflow_failed(mock_live_rag_search):
    class UnrecoverableToolAdapter(InMemoryToolAdapter):
        def verify_build(self, *, recovered: bool) -> dict:
            return {
                "tool": "build.verify",
                "status": "failed",
                "mock_mode": True,
                "recoverable": False,
                "error": "Mock mode: unrecoverable build failure.",
                "summary": "Mock mode: build verification cannot recover.",
            }

    settings = Settings(_env_file=None, adapter_mode="mock")
    workflow = build_workflow(settings, tools=UnrecoverableToolAdapter())
    initial_state = build_initial_state(
        task_id="task-1",
        idea=VALID_IDEA,
        repo_visibility="public",
        demo_mode=True,
        settings=settings,
    )

    final_state = await workflow.ainvoke(initial_state)

    assert final_state["status"] == "failed"
    assert final_state["graph_trace"][-1].node_name == "failed"
    assert final_state["final_report"]["status"] == "failed"


@pytest.mark.asyncio
async def test_workflow_memory_integration(mock_live_rag_search):
    # This proves remember_outcome calls write_memory() and find_similar_builds returns a prior memory
    settings = Settings(_env_file=None, adapter_mode="mock")
    task_store = InMemoryTaskStore()
    service = AgentService(task_store, settings)

    from unittest.mock import patch, MagicMock, AsyncMock
    with patch("agent.rag.store.get_rag_store") as mock_get_store, \
         patch("agent.rag.embed.embed_text", new_callable=AsyncMock) as mock_embed:
        
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_store.search_memories = AsyncMock(return_value=[{"id": "mock_memory"}])
        mock_store.write_memory = AsyncMock()
        mock_embed.return_value = [0.1, 0.2]

        # First run
        response = await service.start_task(
            RunAgentRequest(
                idea="Memory test idea",
                repo_visibility="public",
                demo_mode=True,
            )
        )
        await service.run_task_workflow(response.task_id)
        detail1 = await task_store.get_task(response.task_id)
    
        # Ensure memory_matches from first run contains the mock memory we injected
        assert len(detail1.memory_matches) > 0
        assert detail1.memory_matches[0]["id"] == "mock_memory"
    
        # Verify write_memory was called
        mock_store.write_memory.assert_awaited_once()
        written_memory = mock_store.write_memory.call_args[0][0]
        assert written_memory["task_id"] == response.task_id
        assert written_memory["idea"] == "Memory test idea"
        assert "embedding" in written_memory
    
        # Second run
        response2 = await service.start_task(
            RunAgentRequest(
                idea="Memory test idea 2",
                repo_visibility="public",
                demo_mode=True,
            )
        )
        await service.run_task_workflow(response2.task_id)
        detail2 = await task_store.get_task(response2.task_id)
        
        assert detail2.task.status == TaskStatus.COMPLETED
        assert len(detail2.memory_matches) > 0
        assert detail2.memory_matches[0]["id"] == "mock_memory"
        assert mock_store.write_memory.call_count == 2
