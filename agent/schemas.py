from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_ADDITIONAL_URLS = 5
MAX_UPLOADED_FILES = 5


class TaskStatus(str, Enum):
    STARTED = "started"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadedSourceFile(BaseModel):
    name: str = Field(min_length=1)
    content_type: str
    size_bytes: int = Field(ge=0)

    @field_validator("name", "content_type", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class UploadedSourceFileContent(UploadedSourceFile):
    content: bytes = Field(default=b"", repr=False, exclude=True)


class RunAgentRequest(BaseModel):
    title: str | None = None
    idea: str = Field(min_length=1)
    repo_visibility: Literal["public", "private"]
    demo_mode: bool = False
    source: str | None = None
    primary_rules_url: str | None = None
    additional_urls: list[str] = Field(default_factory=list)
    additional_files: list[UploadedSourceFile] = Field(default_factory=list)
    uploaded_file_contents: list[UploadedSourceFileContent] = Field(
        default_factory=list,
        exclude=True,
    )
    github_connected: bool = False
    github_connection_id: str | None = None

    @field_validator(
        "title",
        "idea",
        "source",
        "primary_rules_url",
        "github_connection_id",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("additional_urls", mode="before")
    @classmethod
    def coerce_additional_urls(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("additional_urls")
    @classmethod
    def trim_additional_urls(cls, value: list[str]) -> list[str]:
        urls = [url.strip() for url in value if url.strip()]
        if len(urls) > MAX_ADDITIONAL_URLS:
            raise ValueError(f"At most {MAX_ADDITIONAL_URLS} additional URLs are supported")
        return urls

    @field_validator("additional_files", "uploaded_file_contents")
    @classmethod
    def limit_uploaded_files(
        cls,
        value: list[UploadedSourceFile] | list[UploadedSourceFileContent],
    ) -> list[UploadedSourceFile] | list[UploadedSourceFileContent]:
        if len(value) > MAX_UPLOADED_FILES:
            raise ValueError(f"At most {MAX_UPLOADED_FILES} uploaded files are supported")
        return value


class RunAgentResponse(BaseModel):
    task_id: str
    status: Literal["started"]


class TaskRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    title: str | None = None
    idea: str
    repo_visibility: Literal["public", "private"]
    demo_mode: bool
    source: str | None = None
    primary_rules_url: str | None = None
    additional_urls: list[str] = Field(default_factory=list)
    additional_files: list[UploadedSourceFile] = Field(default_factory=list)
    github_connected: bool = False
    github_connection_id: str | None = None
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
