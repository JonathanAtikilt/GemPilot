"""Tool call logging adapter with Supabase-compatible REST writes."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tools.http_ssl import default_ssl_context

from tools.schemas import ToolResult


SECRET_MARKERS = ("token", "key", "secret", "password", "authorization")


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if any(marker in key.lower() for marker in SECRET_MARKERS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def _supabase_config() -> tuple[str | None, str | None]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    return url, key


def _post_supabase(table: str, row: dict[str, Any]) -> None:
    url, key = _supabase_config()
    if not url or not key:
        raise RuntimeError("Supabase logging is not configured.")

    endpoint = f"{url.rstrip('/')}/rest/v1/{table}"
    request = Request(
        endpoint,
        data=json.dumps(row).encode("utf-8"),
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urlopen(request, timeout=10, context=default_ssl_context()):
            return
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Supabase HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Supabase request failed: {exc.reason}") from exc


def log_tool_call(
    task_id: str | None,
    tool_name: str,
    input_json: dict[str, Any],
    result: dict[str, Any],
) -> dict:
    """Write a tool call row when Supabase is configured."""

    safe_input = redact_secrets(deepcopy(input_json))
    safe_result = redact_secrets(deepcopy(result))
    row = {
        "task_id": task_id,
        "tool_name": tool_name,
        "input_json": safe_input,
        "output_json": safe_result.get("output", safe_result),
        "status": safe_result.get("status", "unknown"),
        "verification_status": safe_result.get("verification_status", "not_checked"),
        "created_at": datetime.now(UTC).isoformat(),
    }

    url, key = _supabase_config()
    if not url or not key:
        return ToolResult.success(
            "supabase.log_tool_call",
            {
                "logged": False,
                "reason": "Supabase logging is not configured.",
                "row": row,
            },
            verification_status="not_checked",
        ).model_dump(mode="json")

    try:
        _post_supabase("tool_calls", row)
        return ToolResult.success(
            "supabase.log_tool_call",
            {"logged": True, "table": "tool_calls"},
            verification_status="verified",
        ).model_dump(mode="json")
    except Exception as exc:
        return ToolResult.failure(
            "supabase.log_tool_call",
            str(exc),
            {"logged": False, "row": row},
            verification_status="failed",
        ).model_dump(mode="json")


def log_audit_event(
    task_id: str | None,
    step: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict:
    """Write an audit log row when Supabase is configured."""

    safe_data = redact_secrets(deepcopy(data or {}))
    row = {
        "task_id": task_id,
        "step": step,
        "message": message,
        "data": safe_data,
        "created_at": datetime.now(UTC).isoformat(),
    }

    url, key = _supabase_config()
    if not url or not key:
        return ToolResult.success(
            "supabase.log_audit_event",
            {
                "logged": False,
                "reason": "Supabase logging is not configured.",
                "row": row,
            },
            verification_status="not_checked",
        ).model_dump(mode="json")

    try:
        _post_supabase("audit_logs", row)
        return ToolResult.success(
            "supabase.log_audit_event",
            {"logged": True, "table": "audit_logs"},
            verification_status="verified",
        ).model_dump(mode="json")
    except Exception as exc:
        return ToolResult.failure(
            "supabase.log_audit_event",
            str(exc),
            {"logged": False, "row": row},
            verification_status="failed",
        ).model_dump(mode="json")


def log_generated_artifact(
    task_id: str | None,
    artifact_type: str,
    path: str,
    content: str,
    commit_sha: str | None = None,
) -> dict:
    """Write a generated artifact row when Supabase is configured."""

    row = {
        "task_id": task_id,
        "artifact_type": artifact_type,
        "path": path,
        "content": content,
        "commit_sha": commit_sha,
        "created_at": datetime.now(UTC).isoformat(),
    }

    url, key = _supabase_config()
    if not url or not key:
        return ToolResult.success(
            "supabase.log_generated_artifact",
            {
                "logged": False,
                "reason": "Supabase logging is not configured.",
                "row": row,
            },
            verification_status="not_checked",
        ).model_dump(mode="json")

    try:
        _post_supabase("generated_artifacts", row)
        return ToolResult.success(
            "supabase.log_generated_artifact",
            {"logged": True, "table": "generated_artifacts"},
            verification_status="verified",
        ).model_dump(mode="json")
    except Exception as exc:
        return ToolResult.failure(
            "supabase.log_generated_artifact",
            str(exc),
            {"logged": False, "row": row},
            verification_status="failed",
        ).model_dump(mode="json")
