from __future__ import annotations

from agent.config import Settings
from agent.schemas import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    RunAgentRequest,
    RunAgentResponse,
    TaskDetailResponse,
)
from agent.task_store import InMemoryTaskStore


class AgentService:
    def __init__(self, task_store: InMemoryTaskStore, settings: Settings) -> None:
        self._task_store = task_store
        self._settings = settings

    async def start_task(self, request: RunAgentRequest) -> RunAgentResponse:
        task = await self._task_store.create_task(
            request,
            model_name=self._settings.nemotron_fast_model,
        )
        return RunAgentResponse(task_id=task.id, status="started")

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
