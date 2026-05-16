from __future__ import annotations

from json import JSONDecodeError
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

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
FORM_CONTENT_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")


@router.post(
    "/run",
    response_model=RunAgentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_agent(
    request: Request,
    background_tasks: BackgroundTasks,
    service: AgentService = Depends(get_agent_service),
) -> RunAgentResponse:
    run_request = await _parse_run_agent_request(request)
    return await service.start_task(run_request, background_tasks=background_tasks)


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


async def _parse_run_agent_request(request: Request) -> RunAgentRequest:
    content_type = request.headers.get("content-type", "").lower()
    if any(form_type in content_type for form_type in FORM_CONTENT_TYPES):
        payload = await _read_form_payload(request)
    else:
        payload = await _read_json_payload(request)

    try:
        return RunAgentRequest.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


async def _read_json_payload(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        ) from exc

    if not isinstance(payload, dict):
        raise RequestValidationError(
            [
                {
                    "type": "model_attributes_type",
                    "loc": ("body",),
                    "msg": "Input should be a valid object",
                    "input": payload,
                }
            ]
        )
    return payload


async def _read_form_payload(request: Request) -> dict[str, Any]:
    form = await request.form()
    return {
        "idea": form.get("idea"),
        "repo_visibility": form.get("repo_visibility") or "public",
        "demo_mode": form.get("demo_mode") or False,
    }
