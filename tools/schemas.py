"""Shared schemas for MVPilot tool execution and verification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import ErrorDetails


ToolStatus = Literal["success", "failed", "refused", "mock"]
VerificationStatus = Literal["verified", "failed", "not_checked", "mock"]
RepoVisibility = Literal["public", "private"]
MAX_TEXT_FILE_BYTES = 256_000


class FilePayload(BaseModel):
    """A text file to create or update in a generated repository."""

    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(min_length=1)
    content: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/").strip()
        parts = [part for part in normalized.split("/") if part]

        if normalized.startswith("/"):
            raise ValueError("file path must be relative")
        if not parts:
            raise ValueError("file path must not be empty")
        if any(part == ".." for part in parts):
            raise ValueError("file path must not contain '..'")
        if any(part.startswith(".git") for part in parts):
            raise ValueError("file path must not modify git internals")
        if parts[-1] == ".env":
            raise ValueError(".env files must never be committed")

        return "/".join(parts)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        encoded = value.encode("utf-8")
        if len(encoded) > MAX_TEXT_FILE_BYTES:
            raise ValueError(f"file content must be {MAX_TEXT_FILE_BYTES} bytes or smaller")
        if "\x00" in value:
            raise ValueError("binary file content is not supported")
        return value


class ToolResult(BaseModel):
    """Common result shape returned by every Person 3 tool."""

    tool_name: str = Field(min_length=1)
    status: ToolStatus
    output: dict[str, Any] = Field(default_factory=dict)
    verification_status: VerificationStatus = "not_checked"
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def success(
        cls,
        tool_name: str,
        output: dict[str, Any],
        verification_status: VerificationStatus = "verified",
    ) -> "ToolResult":
        return cls(
            tool_name=tool_name,
            status="success",
            output=output,
            verification_status=verification_status,
        )

    @classmethod
    def failure(
        cls,
        tool_name: str,
        error: str,
        output: dict[str, Any] | None = None,
        verification_status: VerificationStatus = "failed",
    ) -> "ToolResult":
        return cls(
            tool_name=tool_name,
            status="failed",
            output=output or {},
            verification_status=verification_status,
            error=error,
        )

    @classmethod
    def refused(cls, tool_name: str, error: str, output: dict[str, Any] | None = None) -> "ToolResult":
        return cls(
            tool_name=tool_name,
            status="refused",
            output=output or {},
            verification_status="not_checked",
            error=error,
        )

    @classmethod
    def mock(cls, tool_name: str, output: dict[str, Any]) -> "ToolResult":
        return cls(
            tool_name=tool_name,
            status="mock",
            output=output | {"mock": True},
            verification_status="mock",
        )


class CreateRepoRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    repo_name: str = Field(min_length=1)
    description: str = ""
    visibility: RepoVisibility = "public"


class CommitFilesRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    repo_name: str = Field(min_length=1)
    files: list[FilePayload] = Field(min_length=1)
    message: str = Field(min_length=1)


class VerificationResult(BaseModel):
    commit_sha: str
    verified: bool
    files_changed: list[str] = Field(default_factory=list)
    error: str | None = None


class RepoHealthResult(BaseModel):
    repo_name: str
    healthy: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)
    error: str | None = None


class BlockerResult(BaseModel):
    has_blocker: bool
    blocker_type: str | None = None
    summary: str | None = None
    recommended_fix: str | None = None


def safe_validation_errors(errors: list[ErrorDetails]) -> list[dict[str, Any]]:
    """Convert Pydantic errors into JSON-safe dictionaries."""

    safe_errors: list[dict[str, Any]] = []
    for error in errors:
        safe_error = dict(error)
        if "ctx" in safe_error:
            safe_error["ctx"] = {key: str(value) for key, value in safe_error["ctx"].items()}
        safe_errors.append(safe_error)
    return safe_errors
