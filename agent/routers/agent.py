from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from agent.dependencies import get_agent_service
from agent.schemas import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    RunAgentRequest,
    RunAgentResponse,
    TaskDetailResponse,
)
from agent.service import AgentService
from agent.task_store import ApprovalNotFoundError, TaskNotFoundError

router = APIRouter(prefix="/agent")


@router.post(
    "/run",
    response_model=RunAgentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_agent(
    request: RunAgentRequest,
    background_tasks: BackgroundTasks,
    service: AgentService = Depends(get_agent_service),
) -> RunAgentResponse:
    return await service.start_task(request, background_tasks=background_tasks)


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: str,
    service: AgentService = Depends(get_agent_service),
) -> TaskDetailResponse:
    try:
        return await service.get_task_detail(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from exc


@router.post("/approve", response_model=ApprovalDecisionResponse)
async def approve_action(
    request: ApprovalDecisionRequest,
    service: AgentService = Depends(get_agent_service),
) -> ApprovalDecisionResponse:
    try:
        return await service.approve_action(request)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from exc
    except ApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found",
        ) from exc
