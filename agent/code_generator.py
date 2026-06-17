"""
Multi-stage code generation pipeline.

Runs 5 sequential LLM calls to produce a complete, product-specific repository:
  Stage 1 – Database  : ORM models, schema DDL, seed data
  Stage 2 – Backend   : FastAPI routes, services, auth, tests
  Stage 3 – Frontend  : React pages, components, hooks, API client
  Stage 4 – Docs      : README, API spec, architecture, deploy guide
  Stage 5 – Demo Video: script, storyboard, walkthrough, outline, voiceover

Each stage receives the outputs of the previous stages as context, so the
frontend generator knows the exact backend route paths, and the docs generator
can document the full file tree.
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from agent.config import Settings
    from agent.model_client import ModelClient

from agent.model_outputs import GeneratedFileBatchOutput
from agent.prompts import (
    build_backend_generation_prompt,
    build_database_generation_prompt,
    build_demo_video_generation_prompt,
    build_docs_generation_prompt,
    build_frontend_generation_prompt,
)

logger = logging.getLogger(__name__)

_STANDARD_STAGES = ("database", "backend", "frontend", "docs", "demo")
_BACKEND_STAGE_HINTS = frozenset(
    {
        "backend",
        "cli_core",
        "commands",
        "analytics_api",
        "extension_core",
        "content_scripts",
        "game_server",
        "api",
    }
)
_FRONTEND_STAGE_HINTS = frozenset(
    {
        "frontend",
        "static_site",
        "content_sections",
        "popup_ui",
        "game_client",
    }
)
_DATABASE_STAGE_HINTS = frozenset({"database"})


def _generation_stages(
    architecture: dict[str, Any],
    product_brief: dict[str, Any],
) -> tuple[str, ...]:
    """Return LLM generation stages appropriate for the classified architecture."""
    validation = architecture.get("validation_profile") or {}
    impl = [
        str(stage).lower()
        for stage in (architecture.get("implementation_stages") or [])
    ]

    if impl:
        include_db = any(stage in _DATABASE_STAGE_HINTS for stage in impl)
        include_backend = any(stage in _BACKEND_STAGE_HINTS for stage in impl)
        include_frontend = any(stage in _FRONTEND_STAGE_HINTS for stage in impl)
    else:
        include_db = bool(
            validation.get("check_database_models", product_brief.get("database_required", True))
        )
        include_backend = bool(
            validation.get("check_backend_routes", product_brief.get("backend_required", True))
        )
        include_frontend = bool(
            validation.get("check_frontend_routes", product_brief.get("frontend_required", True))
        )

    stages: list[str] = []
    if include_db:
        stages.append("database")
    if include_backend:
        stages.append("backend")
    if include_frontend:
        stages.append("frontend")
    stages.extend(["docs", "demo"])
    return tuple(stages or _STANDARD_STAGES)


async def run_staged_generation(
    *,
    model_client: "ModelClient",
    settings: "Settings",
    idea: str,
    product_brief: dict[str, Any],
    stack: dict[str, Any],
    architecture: dict[str, Any],
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Run profile-aware staged generation with retry and architecture simplification."""
    attempts: list[tuple[str, dict[str, Any]]] = [
        ("full", architecture),
        ("simplified", _simplify_architecture(architecture)),
        ("minimal", _simplify_architecture(architecture, minimal=True)),
    ]
    last_mode = "degraded"
    last_traces: list[str] = []
    last_artifacts: list[dict[str, Any]] = []

    for attempt_name, arch in attempts:
        artifacts, mode, traces = await _run_staged_generation_once(
            model_client=model_client,
            settings=settings,
            idea=idea,
            product_brief=product_brief,
            stack=stack,
            architecture=arch,
        )
        last_artifacts, last_mode, last_traces = artifacts, mode, traces
        traces.insert(0, f"generation_attempt={attempt_name} files={len(artifacts)} mode={mode}")
        if artifacts and mode == "live":
            return artifacts, mode, traces
        if artifacts and attempt_name == "minimal":
            return artifacts, mode, traces
    return last_artifacts, last_mode, last_traces


def _simplify_architecture(architecture: dict[str, Any], *, minimal: bool = False) -> dict[str, Any]:
    simplified = dict(architecture)
    stages = [
        str(stage)
        for stage in (architecture.get("implementation_stages") or [])
        if str(stage).strip()
    ]
    if minimal:
        keep = {"docs", "demo", "cli_core", "commands", "api_core", "routes", "static_site"}
        simplified["implementation_stages"] = [s for s in stages if s in keep] or ["docs", "demo"]
    else:
        drop = {"database", "frontend", "analytics_api", "popup_ui", "content_scripts"}
        simplified["implementation_stages"] = [s for s in stages if s not in drop] or stages
    profile = dict(simplified.get("validation_profile") or {})
    profile["check_database_models"] = False if not minimal else profile.get("check_database_models", False)
    profile["check_frontend_routes"] = False if minimal else profile.get("check_frontend_routes", True)
    simplified["validation_profile"] = profile
    return simplified


async def _run_staged_generation_once(
    *,
    model_client: "ModelClient",
    settings: "Settings",
    idea: str,
    product_brief: dict[str, Any],
    stack: dict[str, Any],
    architecture: dict[str, Any],
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Run profile-aware staged code generation.

    Returns
    -------
    artifacts : list[dict]
        Sorted, deduplicated list of ``{name, kind, summary, content}`` dicts.
    overall_mode : str
        ``"live"`` if every stage succeeded with the live LLM; otherwise the
        worst degraded mode seen across stages.
    decision_traces : list[str]
        Aggregated decision-trace lines from all stages.
    """
    by_name: dict[str, dict[str, Any]] = {}
    overall_mode = "live"
    all_traces: list[str] = []
    stages = _generation_stages(architecture, product_brief)
    all_traces.append(f"Generation stages selected: {', '.join(stages)}")

    stage_counts: dict[str, int] = {stage: 0 for stage in stages}

    for stage in stages:
        if stage == "database":
            files, mode, traces = await _run_stage(
                model_client=model_client,
                settings=settings,
                purpose="generate_database",
                prompt=build_database_generation_prompt(
                    idea=idea,
                    product_brief=product_brief,
                    stack=stack,
                    architecture=architecture,
                ),
            )
        elif stage == "backend":
            files, mode, traces = await _run_stage(
                model_client=model_client,
                settings=settings,
                purpose="generate_backend",
                prompt=build_backend_generation_prompt(
                    idea=idea,
                    product_brief=product_brief,
                    stack=stack,
                    architecture=architecture,
                    db_file_names=list(by_name.keys()),
                ),
            )
        elif stage == "frontend":
            files, mode, traces = await _run_stage(
                model_client=model_client,
                settings=settings,
                purpose="generate_frontend",
                prompt=build_frontend_generation_prompt(
                    idea=idea,
                    product_brief=product_brief,
                    stack=stack,
                    architecture=architecture,
                    backend_routes=(
                        product_brief.get("api_routes")
                        or architecture.get("api_design")
                        or []
                    ),
                    data_entities=product_brief.get("data_entities"),
                ),
            )
        elif stage == "docs":
            files, mode, traces = await _run_stage(
                model_client=model_client,
                settings=settings,
                purpose="generate_docs",
                prompt=build_docs_generation_prompt(
                    idea=idea,
                    product_brief=product_brief,
                    stack=stack,
                    architecture=architecture,
                    generated_file_names=list(by_name.keys()),
                ),
            )
        else:
            files, mode, traces = await _run_stage(
                model_client=model_client,
                settings=settings,
                purpose="generate_demo_video",
                prompt=build_demo_video_generation_prompt(
                    idea=idea,
                    product_brief=product_brief,
                    stack=stack,
                    architecture=architecture,
                    generated_file_names=list(by_name.keys()),
                ),
            )

        _merge(by_name, files)
        all_traces.extend(traces)
        stage_counts[stage] = len(files)
        if mode != "live":
            overall_mode = mode

    artifacts = [by_name[name] for name in sorted(by_name)]
    counts = ", ".join(f"{stage}={stage_counts.get(stage, 0)}" for stage in stages)
    all_traces.append(
        f"Staged generation complete: {len(artifacts)} files across {len(stages)} stages ({counts})."
    )
    return artifacts, overall_mode, all_traces


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _run_stage(
    *,
    model_client: "ModelClient",
    settings: "Settings",
    purpose: str,
    prompt: str,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Call the LLM for one generation stage. Returns (files, mode, traces)."""
    try:
        result = await model_client.complete_structured(
            purpose=purpose,
            model=settings.llm_model_name,
            prompt=prompt,
            response_model=GeneratedFileBatchOutput,
            max_tokens=settings.llm_max_tokens_for(purpose),
            reasoning_effort=settings.llm_reasoning_effort,
        )
        files = _normalize(result.output.files, stage=purpose)
        traces = list(result.output.decision_trace or [])
        traces.insert(0, f"{purpose}: {len(files)} file(s) [{result.mode}].")
        return files, result.mode, traces
    except Exception as exc:
        logger.warning("Code generation stage %s failed: %s", purpose, exc)
        if not settings.allow_idea_aware_partial:
            raise RuntimeError(
                f"Live-only mode: code generation stage {purpose} failed."
            ) from exc
        return [], "degraded", [f"{purpose}: stage skipped — {exc}"]


def _normalize(raw_files: list[Any], *, stage: str) -> list[dict[str, Any]]:
    """Convert model output objects to plain dicts, dropping empties."""
    result: list[dict[str, Any]] = []
    for f in raw_files:
        name = str(getattr(f, "name", "") or "").strip()
        content = str(getattr(f, "content", "") or "").strip()
        if not name or not content:
            continue
        # Skip directory placeholders and literal secret files
        last_segment = name.split("/")[-1]
        if name.endswith("/") or last_segment == ".env":
            continue
        result.append(
            {
                "name": name,
                "kind": str(getattr(f, "kind", "") or _kind(name)),
                "summary": str(getattr(f, "summary", "") or f"Generated by {stage}."),
                "content": content,
            }
        )
    return result


def _merge(
    target: dict[str, dict[str, Any]],
    files: list[dict[str, Any]],
) -> None:
    for f in files:
        name = f.get("name", "")
        if name:
            target[name] = f


def _kind(name: str) -> str:
    if "." not in name:
        return "code"
    ext = name.rsplit(".", 1)[-1].lower()
    return {
        "py": "python",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "css": "css",
        "html": "html",
        "md": "markdown",
        "sql": "sql",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "txt": "text",
        "sh": "shell",
        "toml": "toml",
        "env": "text",
    }.get(ext, "code")
