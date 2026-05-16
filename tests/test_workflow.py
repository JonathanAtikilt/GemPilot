import pytest

from agent.config import Settings
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


@pytest.mark.asyncio
async def test_full_workflow_completes_with_expected_timeline():
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
    assert detail.build_context.get("mode") == "mock"
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
async def test_unrecoverable_tool_result_marks_workflow_failed():
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
