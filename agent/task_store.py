from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4

from agent.schemas import (
    ApprovalDecisionRequest,
    ApprovalRecord,
    RunAgentRequest,
    TaskDetailResponse,
    TaskRecord,
    TaskStatus,
    UploadedSourceFile,
    UploadedSourceFileContent,
)


class TaskNotFoundError(KeyError):
    """Raised when a requested task does not exist."""


class ApprovalNotFoundError(KeyError):
    """Raised when a requested approval does not exist for a task."""


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: dict[str, TaskDetailResponse] = {}
        self._uploaded_file_contents: dict[str, list[UploadedSourceFileContent]] = {}

    async def create_task(
        self,
        request: RunAgentRequest,
    ) -> TaskRecord:
        task_id = str(uuid4())
        now = self._now()
        additional_files = list(request.additional_files)
        if not additional_files and request.uploaded_file_contents:
            additional_files = [
                UploadedSourceFile.model_validate(file.model_dump())
                for file in request.uploaded_file_contents
            ]

        task = TaskRecord(
            id=task_id,
            title=request.title,
            idea=request.idea,
            repo_visibility=request.repo_visibility,
            demo_mode=request.demo_mode,
            source=request.source,
            primary_rules_url=request.primary_rules_url,
            additional_urls=list(request.additional_urls),
            additional_files=additional_files,
            github_connected=request.github_connected,
            github_connection_id=request.github_connection_id,
            status=TaskStatus.STARTED,
            created_at=now,
            updated_at=now,
        )
        detail = TaskDetailResponse(task=task)

        async with self._lock:
            self._tasks = {**self._tasks, task_id: detail}
            self._uploaded_file_contents = {
                **self._uploaded_file_contents,
                task_id: list(request.uploaded_file_contents),
            }

        return task.model_copy(deep=True)

    async def get_task(self, task_id: str) -> TaskDetailResponse:
        async with self._lock:
            detail = self._tasks.get(task_id)
            if detail is None:
                raise TaskNotFoundError(task_id)
            return detail.model_copy(deep=True)

    async def get_uploaded_file_contents(
        self,
        task_id: str,
    ) -> list[UploadedSourceFileContent]:
        async with self._lock:
            if task_id not in self._tasks:
                raise TaskNotFoundError(task_id)
            return [
                file.model_copy(deep=True)
                for file in self._uploaded_file_contents.get(task_id, [])
            ]

    async def snapshot_task(
        self,
        task_id: str,
        state: Mapping[str, Any],
    ) -> TaskDetailResponse:
        now = self._now()

        async with self._lock:
            current = self._tasks.get(task_id)
            if current is None:
                raise TaskNotFoundError(task_id)

            updated_task = current.task.model_copy(
                update={
                    "status": TaskStatus(state.get("status", current.task.status)),
                    "updated_at": now,
                }
            )
            updated_detail = TaskDetailResponse(
                task=updated_task,
                agent_steps=list(state.get("agent_steps", current.agent_steps)),
                retrieved_docs=list(state.get("retrieved_docs", current.retrieved_docs)),
                build_context=state.get("build_context", current.build_context),
                memory_matches=list(state.get("memory_matches", current.memory_matches)),
                tool_calls=list(state.get("tool_calls", current.tool_calls)),
                approvals=current.approvals,
                generated_artifacts=list(
                    state.get("generated_artifacts", current.generated_artifacts)
                ),
                graph_trace=list(state.get("graph_trace", current.graph_trace)),
                final_report=state.get("final_report", current.final_report),
            )
            self._tasks = {**self._tasks, task_id: updated_detail}

        return updated_detail.model_copy(deep=True)

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
