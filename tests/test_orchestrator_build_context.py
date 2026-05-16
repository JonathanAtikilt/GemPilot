import pytest

from agent.adapters import InMemoryRagMemoryAdapter
from agent.config import Settings
from agent.workflow import build_initial_state, build_workflow


@pytest.mark.asyncio
async def test_retrieve_context_node_populates_build_context_for_nemotron() -> None:
    settings = Settings(_env_file=None, adapter_mode="mock")
    rag = InMemoryRagMemoryAdapter()
    workflow = build_workflow(settings, retrieval=rag)
    state = build_initial_state(
        task_id="task-build-context",
        idea="Autonomous hackathon teammate with RAG and GitHub tools",
        repo_visibility="public",
        demo_mode=True,
        settings=settings,
    )

    update = await workflow.nodes["retrieve_context"].ainvoke(state)
    merged = {**state, **update}

    build_context = merged["build_context"]
    assert build_context["mode"] == "mock"
    assert len(build_context["requiredDeliverables"]) >= 1
    assert len(build_context["allowedToolsAndAPIs"]) >= 1
    assert len(build_context["requiredRepositoryFormat"]) >= 1
    assert len(build_context["requiredDemoFormat"]) >= 1
    assert len(build_context["requiredTechStackPieces"]) >= 1
    assert build_context["scopeWarnings"]
    assert merged["retrieved_docs"]
    assert merged["memory_matches"]

    retrieve_step = merged["agent_steps"][-1]
    assert retrieve_step.node_name == "retrieve_context"
    assert "build context" in retrieve_step.message.lower()
