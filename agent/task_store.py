from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from agent.schemas import (
    AgentStep,
    ApprovalDecisionRequest,
    ApprovalRecord,
    RunAgentRequest,
    TaskDetailResponse,
    TaskRecord,
    TaskStatus,
)


class TaskNotFoundError(KeyError):
    """Raised when a requested task does not exist."""


class ApprovalNotFoundError(KeyError):
    """Raised when a requested approval does not exist for a task."""


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: dict[str, TaskDetailResponse] = {}

    async def create_task(
        self,
        request: RunAgentRequest,
        *,
        model_name: str,
    ) -> TaskRecord:
        task_id = str(uuid4())
        now = self._now()
        task = TaskRecord(
            id=task_id,
            idea=request.idea,
            repo_visibility=request.repo_visibility,
            demo_mode=request.demo_mode,
            status=TaskStatus.STARTED,
            created_at=now,
            updated_at=now,
        )
        initial_step = AgentStep(
            node_name="receive_idea",
            status="completed",
            message="Received the idea and initialized deterministic mock task state.",
            model=model_name,
            decision_trace=[
                "Accepted the idea payload.",
                "Created the stable dashboard response shell.",
                "Deferred LangGraph execution to the next backend slice.",
            ],
            timestamp=now,
        )
        detail = TaskDetailResponse(
            task=task,
            agent_steps=[initial_step],
            graph_trace=[initial_step],
        )

        async with self._lock:
            self._tasks = {**self._tasks, task_id: detail}

        return task.model_copy(deep=True)

    async def get_task(self, task_id: str) -> TaskDetailResponse:
        async with self._lock:
            detail = self._tasks.get(task_id)
            if detail is None:
                raise TaskNotFoundError(task_id)
            return detail.model_copy(deep=True)

    async def seed_pending_approval(
        self,
        *,
        task_id: str,
        proposed_action: str,
        risk_level: str,
    ) -> ApprovalRecord:
        now = self._now()
        approval = ApprovalRecord(
            approval_id=str(uuid4()),
            task_id=task_id,
            proposed_action=proposed_action,
            risk_level=risk_level,
            created_at=now,
        )

        async with self._lock:
            current = self._tasks.get(task_id)
            if current is None:
                raise TaskNotFoundError(task_id)

            updated_task = current.task.model_copy(update={"updated_at": now})
            updated_detail = current.model_copy(
                update={
                    "task": updated_task,
                    "approvals": [*current.approvals, approval],
                },
                deep=True,
            )
            self._tasks = {**self._tasks, task_id: updated_detail}

        return approval.model_copy(deep=True)

    async def resolve_approval(
        self,
        request: ApprovalDecisionRequest,
    ) -> ApprovalRecord:
        now = self._now()

        async with self._lock:
            current = self._tasks.get(request.task_id)
            if current is None:
                raise TaskNotFoundError(request.task_id)

            if not any(
                approval.approval_id == request.approval_id
                for approval in current.approvals
            ):
                raise ApprovalNotFoundError(request.approval_id)

            updated_approvals = [
                approval.model_copy(
                    update={
                        "status": request.decision,
                        "approved_by": request.approved_by,
                        "resolved_at": now,
                    }
                )
                if approval.approval_id == request.approval_id
                else approval
                for approval in current.approvals
            ]
            updated_task = current.task.model_copy(update={"updated_at": now})
            updated_detail = current.model_copy(
                update={"task": updated_task, "approvals": updated_approvals},
                deep=True,
            )
            self._tasks = {**self._tasks, request.task_id: updated_detail}

        for approval in updated_approvals:
            if approval.approval_id == request.approval_id:
                return approval.model_copy(deep=True)

        raise ApprovalNotFoundError(request.approval_id)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
