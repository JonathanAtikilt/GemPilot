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
_CODE_GEN_PURPOSES = frozenset(
    {
        "generate_database",
        "generate_backend",
        "generate_frontend",
        "generate_docs",
        "generate_demo_video",
    }
)

_STAGE_EXACT_PATHS: dict[str, frozenset[str]] = {
    "generate_database": frozenset(
        {
            "backend/db.py",
            "backend/models.py",
            "docs/DATABASE_SCHEMA.sql",
            "scripts/seed_data.py",
            "data/seed.json",
        }
    ),
    "generate_backend": frozenset(
        {
            "backend/main.py",
            "backend/services.py",
            "backend/__init__.py",
            "requirements.txt",
            "tests/test_backend.py",
            "tests/test_api.py",
            "docs/API_SPEC.md",
        }
    ),
    "generate_frontend": frozenset(
        {
            "package.json",
            "index.html",
            "App.tsx",
            "index.js",
            "src/main.jsx",
            "src/App.jsx",
            "src/lib/api.js",
            "src/state/projectState.js",
            "src/styles.css",
            "frontend/index.html",
            "frontend/src/main.js",
            "frontend/src/styles.css",
        }
    ),
    "generate_docs": frozenset(
        {
            "README.md",
            "docs/PROJECT_PLAN.md",
            "docs/ARCHITECTURE.md",
            "docs/TESTING_STRATEGY.md",
            "docs/DEPLOY.md",
            "docs/AGENT_LOG.md",
            "docs/BUILD_LOG.md",
            "docs/KNOWN_LIMITATIONS.md",
            "docs/WALKTHROUGH.md",
            ".env.example",
        }
    ),
    "generate_demo_video": frozenset(
        {
            "demo/script.md",
            "demo/storyboard.md",
            "demo/demo_walkthrough.md",
            "demo/video_outline.md",
            "demo/voiceover.md",
            "demo/demo_script.md",
            "docs/HACKATHON_SUBMISSION.md",
        }
    ),
}


def project_generator_stage_batch(
    *,
    purpose: str,
    idea: str,
    title: str | None,
    resolved_stack: str,
    architecture_plan: dict[str, Any] | None = None,
    source_warnings: list[dict[str, str]] | None = None,
    target_users: str | None = None,
    required_features: list[str] | None = None,
    tech_stack_preference: str | None = None,
    project_requirements: dict[str, Any] | None = None,
    target_platform: str | None = None,
    is_hackathon_mode: bool = False,
    mode: str = "degraded",
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    """Return a stage file batch from the classification-driven project generator."""
    from agent.generated_project import build_project_artifacts
    from agent.model_outputs import GeneratedFileBatchOutput, GeneratedFileWithContent

    if purpose not in _CODE_GEN_PURPOSES:
        raise ValueError(f"Unsupported code generation purpose: {purpose}")

    artifacts = build_project_artifacts(
        idea=idea,
        title=title,
        resolved_stack=resolved_stack,
        architecture_plan=architecture_plan,
        source_warnings=source_warnings,
        target_users=target_users,
        required_features=required_features,
        tech_stack_preference=tech_stack_preference,
        project_requirements=project_requirements,
        target_platform=target_platform,
        is_hackathon_mode=is_hackathon_mode,
    )
    exact = _STAGE_EXACT_PATHS.get(purpose, frozenset())
    selected = [
        artifact
        for artifact in artifacts
        if artifact["name"] in exact
        or (
            purpose == "generate_backend"
            and artifact["name"].startswith("cli/")
        )
        or (
            purpose == "generate_frontend"
            and (
                artifact["name"].startswith("extension/")
                or artifact["name"] in {"manifest.json", "background.js", "popup.html", "popup.js", "content.js"}
            )
        )
    ]
    if not selected and purpose == "generate_docs":
        selected = [artifact for artifact in artifacts if artifact["name"] == "README.md"]
    files = [
        GeneratedFileWithContent(
            name=str(artifact["name"]),
            kind=str(artifact.get("kind") or "code"),
            summary=str(artifact.get("summary") or "Generated from classified project plan."),
            content=str(artifact.get("content") or ""),
        )
        for artifact in selected
        if str(artifact.get("content") or "").strip()
    ]
    stage_key = purpose.replace("generate_", "")
    trace_reason = fallback_reason or "Used classification-driven project generator output for this stage."
    return GeneratedFileBatchOutput(
        stage=stage_key,
        files=files,
        mode=mode,  # type: ignore[arg-type]
        decision_trace=[
            f"{purpose}: emitted {len(files)} file(s) from classified project generator.",
            trace_reason,
        ],
    ).model_dump()


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
    stages.append("docs")
    if product_brief.get("is_hackathon_mode") or product_brief.get("demo_mode"):
        stages.append("demo")
    return tuple(stages or ("docs",))


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
        if artifacts:
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
