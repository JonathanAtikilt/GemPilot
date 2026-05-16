from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent.rag.url_utils import collect_source_urls


class TaskStatus(str, Enum):
    STARTED = "started"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class RunAgentRequest(BaseModel):
    idea: str = Field(min_length=1)
    repo_visibility: Literal["public", "private"]
    demo_mode: bool = False
    primary_rules_url: str | None = None
    rules_url: str | None = None
    additional_urls: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)

    @field_validator("idea", mode="before")
    @classmethod
    def trim_idea(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("additional_urls", mode="before")
    @classmethod
    def coerce_additional_urls(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @model_validator(mode="after")
    def merge_source_urls(self) -> RunAgentRequest:
        merged = collect_source_urls(
            source_urls=self.source_urls,
            primary_rules_url=self.primary_rules_url,
            rules_url=self.rules_url,
            additional_urls=self.additional_urls,
        )
        self.source_urls = merged
        if merged and not self.primary_rules_url:
            self.primary_rules_url = merged[0]
        return self


class RunAgentResponse(BaseModel):
    task_id: str
    status: Literal["started"]


class TaskRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    idea: str
    repo_visibility: Literal["public", "private"]
    demo_mode: bool
    source_urls: list[str] = Field(default_factory=list)
    status: TaskStatus
    created_at: datetime
    updated_at: datetime


class AgentStep(BaseModel):
    node_name: str
    status: str
    message: str
    model: str | None = None
    prompt_purpose: str | None = None
    model_mode: Literal["mock", "live", "fallback"] | None = None
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
    build_context: dict[str, Any] | None = None
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
