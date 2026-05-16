from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import BackgroundTasks

from agent.config import Settings
from agent.schemas import (
    AgentStep,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    RunAgentRequest,
    RunAgentResponse,
    TaskStatus,
    TaskDetailResponse,
)
from agent.task_store import InMemoryTaskStore
from agent.workflow import build_initial_state, build_workflow


class AgentService:
    def __init__(self, task_store: InMemoryTaskStore, settings: Settings) -> None:
        self._task_store = task_store
        self._settings = settings

    async def start_task(
        self,
        request: RunAgentRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> RunAgentResponse:
        task = await self._task_store.create_task(request)
        if background_tasks is not None:
            background_tasks.add_task(self.run_task_workflow, task.id)
        return RunAgentResponse(task_id=task.id, status="started")

    async def run_task_workflow(self, task_id: str) -> None:
        detail = await self._task_store.get_task(task_id)
        state = build_initial_state(
            task_id=task_id,
            idea=detail.task.idea,
            repo_visibility=detail.task.repo_visibility,
            demo_mode=detail.task.demo_mode,
            source_urls=detail.task.source_urls,
            settings=self._settings,
        )
        
        from agent.live_adapters import LiveRagMemoryAdapter

        rag = LiveRagMemoryAdapter()
        if self._settings.mock_mode:
            from agent.adapters import InMemoryAuditAdapter, InMemoryToolAdapter

            tools = InMemoryToolAdapter()
            audit = InMemoryAuditAdapter(model_name=self._settings.nemotron_fast_model)
        else:
            from agent.live_adapters import LiveAuditAdapter, LiveToolAdapter

            tools = LiveToolAdapter()
            audit = LiveAuditAdapter(model_name=self._settings.nemotron_fast_model)

        workflow = build_workflow(self._settings, tools=tools, retrieval=rag, audit=audit)

        try:
            async for snapshot in workflow.astream(state, stream_mode="values"):
                await self._task_store.snapshot_task(task_id, snapshot)
        except Exception as exc:
            current_detail = await self._task_store.get_task(task_id)
            failed_state = self._build_unexpected_failure_state(current_detail, exc)
            await self._task_store.snapshot_task(task_id, failed_state)

    async def get_task_detail(self, task_id: str) -> TaskDetailResponse:
        return await self._task_store.get_task(task_id)

    async def approve_action(
        self,
        request: ApprovalDecisionRequest,
    ) -> ApprovalDecisionResponse:
        approval = await self._task_store.resolve_approval(request)
        return ApprovalDecisionResponse(
            task_id=approval.task_id,
            approval_id=approval.approval_id,
            status=approval.status,
            approved_by=approval.approved_by or request.approved_by,
        )

    def _build_unexpected_failure_state(
        self,
        detail: TaskDetailResponse,
        exc: Exception,
    ) -> dict[str, Any]:
        message = "Workflow failed before the graph could finish."
        step = AgentStep(
            node_name="failed",
            status="failed",
            message=message,
            model=self._settings.nemotron_fast_model,
            decision_trace=[
                "Mock mode: deterministic failure fallback.",
                f"Captured unexpected error: {exc.__class__.__name__}.",
            ],
            timestamp=datetime.now(UTC),
        )
        return {
            "status": TaskStatus.FAILED,
            "agent_steps": [*detail.agent_steps, step],
            "retrieved_docs": detail.retrieved_docs,
            "build_context": detail.build_context or {},
            "memory_matches": detail.memory_matches,
            "tool_calls": detail.tool_calls,
            "generated_artifacts": detail.generated_artifacts,
            "graph_trace": [*detail.graph_trace, step],
            "final_report": {
                "status": "failed",
                "mode": "mock",
                "model": self._settings.nemotron_fast_model,
                "summary": message,
            },
        }
