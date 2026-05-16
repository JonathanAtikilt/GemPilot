import pytest
from unittest.mock import AsyncMock, patch

from agent.config import Settings
from agent.live_adapters import LiveRagMemoryAdapter
from agent.workflow import build_initial_state, build_workflow


@pytest.mark.asyncio
async def test_retrieve_context_indexes_orchestrator_urls_before_build_context(
    mock_live_rag_search,
) -> None:
    settings = Settings(_env_file=None, adapter_mode="mock")
    adapter = LiveRagMemoryAdapter()
    adapter.index_source_urls = AsyncMock(
        return_value={"documentsLoaded": 2, "chunksCreated": 5, "storedIn": "supabase"}
    )

    workflow = build_workflow(settings, retrieval=adapter)
    state = build_initial_state(
        task_id="task-urls",
        idea="Hackathon agent with custom rules URL",
        repo_visibility="public",
        demo_mode=True,
        settings=settings,
        source_urls=["https://hackathon.example.com/rules"],
    )

    with patch(
        "agent.live_adapters.build_build_context_response",
        new_callable=AsyncMock,
    ) as mock_build_context:
        from agent.rag.types import BuildContextResponse, ResolvedTechStack

        mock_build_context.return_value = BuildContextResponse(
            requiredDeliverables=[],
            allowedToolsAndAPIs=[],
            requiredRepositoryFormat=[],
            requiredDemoFormat=[],
            requiredTechStackPieces=[],
            resolvedTechStack=ResolvedTechStack(
                source="default",
                items=[],
                requiredItems=[],
                defaultItems=[],
                reason="test",
            ),
            scopeWarnings=[],
            evidence=[],
        )

        update = await workflow.nodes["retrieve_context"].ainvoke(state)

    adapter.index_source_urls.assert_awaited_once_with(
        ["https://hackathon.example.com/rules"]
    )
    mock_build_context.assert_awaited_once()
    request = mock_build_context.await_args.args[0]
    assert request.optionalParams.sourceUrls == [
        "https://hackathon.example.com/rules"
    ]
    assert request.contextNeeded

    retrieve_step = update["agent_steps"][-1]
    assert any(
        "Indexed 2 orchestrator URL document(s)" in line
        for line in retrieve_step.decision_trace
    )
