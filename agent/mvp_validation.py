"""Backward-compatible validation imports for older callers."""

from __future__ import annotations

from typing import Any

from agent.validate_project import validate_project
from agent.project_validation import build_project_delivery_report


def validate_mvp_output(
    *,
    idea: str,
    intake: dict[str, Any] | None,
    mvp_scope: dict[str, Any] | None,
    repo_plan: dict[str, Any] | None,
    generated_artifacts: list[dict[str, Any]],
    model_modes: list[str],
    require_live_manifest: bool = False,
    manifest_model_mode: str | None = None,
    allow_degraded_manifest: bool = False,
) -> dict[str, Any]:
    return validate_project(
        idea=idea,
        intake=intake,
        project_plan=mvp_scope,
        generated_artifacts=generated_artifacts,
        model_modes=model_modes,
        project_requirements=mvp_scope,
        architecture_plan=repo_plan,
        require_live_manifest=require_live_manifest,
        manifest_model_mode=manifest_model_mode,
        allow_degraded_manifest=allow_degraded_manifest,
    )


def build_delivery_report(
    *,
    idea: str,
    intake: dict[str, Any] | None,
    mvp_scope: dict[str, Any] | None,
    validation: dict[str, Any],
    model_modes: list[str],
    generated_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return build_project_delivery_report(
        idea=idea,
        intake=intake,
        project_requirements=mvp_scope,
        validation=validation,
        model_modes=model_modes,
        generated_artifacts=generated_artifacts,
    )
