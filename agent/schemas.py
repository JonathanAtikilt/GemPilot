from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskStatus(str, Enum):
    STARTED = "started"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class RunAgentRequest(BaseModel):
    idea: str = Field(min_length=1)
    repo_visibility: Literal["public", "private"]
    demo_mode: bool = False

    @field_validator("idea", mode="before")
    @classmethod
    def trim_idea(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class RunAgentResponse(BaseModel):
    task_id: str
    status: Literal["started"]


class TaskRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    idea: str
    repo_visibility: Literal["public", "private"]
    demo_mode: bool
    status: TaskStatus
    created_at: datetime
    updated_at: datetime


class AgentStep(BaseModel):
    node_name: str
    status: str
    message: str
    model: str | None = None
    decision_trace: list[str] = Field(default_factory=list)
    timestamp: datetime


class ApprovalRecord(BaseModel):
    approval_id: str
    task_id: str
    proposed_action: str
    risk_level: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    approved_by: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class TaskDetailResponse(BaseModel):
    task: TaskRecord
    agent_steps: list[AgentStep] = Field(default_factory=list)
    retrieved_docs: list[dict[str, Any]] = Field(default_factory=list)
    memory_matches: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    generated_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    graph_trace: list[AgentStep] = Field(default_factory=list)
    final_report: dict[str, Any] | None = None


class ApprovalDecisionRequest(BaseModel):
    task_id: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    decision: Literal["approved", "rejected"]
    approved_by: str = Field(min_length=1)

    @field_validator("task_id", "approval_id", "approved_by", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ApprovalDecisionResponse(BaseModel):
    task_id: str
    approval_id: str
    status: Literal["approved", "rejected"]
    approved_by: str
