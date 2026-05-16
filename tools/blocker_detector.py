"""Pattern-based blocker detection for demo build logs."""

from __future__ import annotations

from typing import Any

from tools.schemas import BlockerResult, ToolResult


def _flatten_logs(logs: list[dict[str, Any]]) -> str:
    return "\n".join(str(value) for log in logs for value in log.values()).lower()


def detect_blocker(logs: list[dict]) -> dict:
    """Turn build or tool logs into a demo-ready blocker record."""

    if not logs:
        output = BlockerResult(
            has_blocker=False,
            summary="No logs were provided, so no blocker was detected.",
        ).model_dump()
        return ToolResult.success(
            "build.detect_blocker",
            output,
            verification_status="not_checked",
        ).model_dump(mode="json")

    text = _flatten_logs(logs)

    if "/api/analyze" in text and "/api/analyze-referral" in text:
        output = BlockerResult(
            has_blocker=True,
            blocker_type="route_mismatch",
            summary="Frontend called /api/analyze but backend exposes /api/analyze-referral.",
            recommended_fix="Update the frontend fetch call to /api/analyze-referral.",
        ).model_dump()
    elif "modulenotfounderror" in text or "cannot find module" in text or "no module named" in text:
        output = BlockerResult(
            has_blocker=True,
            blocker_type="missing_dependency",
            summary="The build failed because a required dependency is missing.",
            recommended_fix="Add the missing dependency to package.json or requirements.txt and reinstall dependencies.",
        ).model_dump()
    elif "missing env" in text or "environment variable" in text or "keyerror" in text:
        output = BlockerResult(
            has_blocker=True,
            blocker_type="missing_env_var",
            summary="The app expects an environment variable that is not configured.",
            recommended_fix="Document the required environment variable and add it to the runtime configuration.",
        ).model_dump()
    elif "github api" in text and ("failed" in text or "http" in text or "rate limit" in text):
        output = BlockerResult(
            has_blocker=True,
            blocker_type="github_api_failure",
            summary="A GitHub API call failed during tool execution.",
            recommended_fix="Log the failure, retry once if safe, then switch to mock mode if the API remains unavailable.",
        ).model_dump()
    elif "build failed" in text or "exit code 1" in text or "traceback" in text:
        output = BlockerResult(
            has_blocker=True,
            blocker_type="build_failed",
            summary="The build or script execution failed.",
            recommended_fix="Inspect the failing command output, apply the smallest fix, and rerun verification.",
        ).model_dump()
    else:
        output = BlockerResult(
            has_blocker=False,
            summary="No known blocker pattern was detected.",
        ).model_dump()

    return ToolResult.success(
        "build.detect_blocker",
        output,
        verification_status="not_checked",
    ).model_dump(mode="json")
