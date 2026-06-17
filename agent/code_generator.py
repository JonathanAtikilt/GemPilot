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


async def run_staged_generation(
    *,
    model_client: "ModelClient",
    settings: "Settings",
    idea: str,
    product_brief: dict[str, Any],
    stack: dict[str, Any],
    architecture: dict[str, Any],
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Run the 5-stage code-generation pipeline.

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
    by_name: dict[str, dict[str, Any]] = {}  # name → artifact; last write wins
    overall_mode = "live"
    all_traces: list[str] = []

    # ── Stage 1 : Database ────────────────────────────────────────────────────
    db_files, db_mode, db_traces = await _run_stage(
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
    _merge(by_name, db_files)
    all_traces.extend(db_traces)
    if db_mode != "live":
        overall_mode = db_mode

    # ── Stage 2 : Backend ─────────────────────────────────────────────────────
    backend_files, backend_mode, backend_traces = await _run_stage(
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
    _merge(by_name, backend_files)
    all_traces.extend(backend_traces)
    if backend_mode != "live":
        overall_mode = backend_mode

    # ── Stage 3 : Frontend ────────────────────────────────────────────────────
    frontend_files, frontend_mode, frontend_traces = await _run_stage(
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
    _merge(by_name, frontend_files)
    all_traces.extend(frontend_traces)
    if frontend_mode != "live":
        overall_mode = frontend_mode

    # ── Stage 4 : Documentation ───────────────────────────────────────────────
    docs_files, docs_mode, docs_traces = await _run_stage(
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
    _merge(by_name, docs_files)
    all_traces.extend(docs_traces)
    if docs_mode != "live":
        overall_mode = docs_mode

    # ── Stage 5 : Demo Video Materials ────────────────────────────────────────
    demo_files, demo_mode, demo_traces = await _run_stage(
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
    _merge(by_name, demo_files)
    all_traces.extend(demo_traces)
    if demo_mode != "live":
        overall_mode = demo_mode

    artifacts = [by_name[name] for name in sorted(by_name)]
    all_traces.append(
        f"Staged generation complete: {len(artifacts)} files across 5 stages "
        f"(db={len(db_files)}, backend={len(backend_files)}, "
        f"frontend={len(frontend_files)}, docs={len(docs_files)}, "
        f"demo_video={len(demo_files)})."
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
