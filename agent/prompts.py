from __future__ import annotations

import json
from typing import Any


def _json_block(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def build_scope_mvp_prompt(
    *,
    idea: str,
    build_context: dict[str, Any],
    retrieved_docs: list[dict[str, Any]],
    memory_matches: list[dict[str, Any]],
) -> str:
    return (
        "Scope this hackathon idea into one demo-ready MVP.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Structured build context (highest priority — follow critical items first):\n"
        f"{_json_block(build_context)}\n\n"
        f"Retrieved docs:\n{_json_block(retrieved_docs)}\n\n"
        f"Memory matches:\n{_json_block(memory_matches)}\n\n"
        "Honor required deliverables, allowed tools/APIs, repository format, demo format, "
        "tech stack pieces, and scope warnings from build context. "
        "Return target user, must-have features, demo boundary, mode, and a short decision trace."
    )


def build_plan_repo_prompt(
    *,
    idea: str,
    mvp_scope: dict[str, Any],
    build_context: dict[str, Any],
) -> str:
    return (
        "Plan the smallest generated repository package for this MVP.\n\n"
        f"Idea:\n{idea}\n\n"
        f"MVP scope:\n{_json_block(mvp_scope)}\n\n"
        f"Structured build context:\n{_json_block(build_context)}\n\n"
        "Align files and layout with requiredRepositoryFormat and allowedToolsAndAPIs. "
        "Return files, test plan, architecture notes, mode, and decision trace."
    )


def build_file_manifest_prompt(
    *,
    idea: str,
    repo_plan: dict[str, Any],
) -> str:
    return (
        "Create the generated artifact manifest for the MVP repo.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Repo plan:\n{_json_block(repo_plan)}\n\n"
        "Return artifact names, kinds, summaries, optional content, mode, and "
        "decision trace."
    )


def build_blocker_analysis_prompt(
    *,
    idea: str,
    tool_result: dict[str, Any],
) -> str:
    return (
        "Analyze this blocked build result and decide whether it can recover.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Tool result:\n{_json_block(tool_result)}\n\n"
        "Return blocker type, severity, recoverable flag, root cause, recovery "
        "plan, and decision trace."
    )


def build_final_readme_prompt(
    *,
    idea: str,
    mvp_scope: dict[str, Any],
    repo_plan: dict[str, Any],
    generated_artifacts: list[dict[str, Any]],
) -> str:
    return (
        "Write the final README content for the generated MVP package.\n\n"
        f"Idea:\n{idea}\n\n"
        f"MVP scope:\n{_json_block(mvp_scope)}\n\n"
        f"Repo plan:\n{_json_block(repo_plan)}\n\n"
        f"Artifacts:\n{_json_block(generated_artifacts)}\n\n"
        "Return title, README markdown content, setup steps, and decision trace."
    )


def build_demo_script_prompt(
    *,
    idea: str,
    blocker_analysis: dict[str, Any] | None,
) -> str:
    return (
        "Write a short demo script for judges.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Blocker analysis:\n{_json_block(blocker_analysis or {})}\n\n"
        "Return title, script content, demo beats, and decision trace."
    )


def build_pitch_prompt(
    *,
    idea: str,
    final_readme: dict[str, Any],
    demo_script: dict[str, Any],
) -> str:
    return (
        "Write the final hackathon pitch for this package.\n\n"
        f"Idea:\n{idea}\n\n"
        f"README:\n{_json_block(final_readme)}\n\n"
        f"Demo script:\n{_json_block(demo_script)}\n\n"
        "Return title, tagline, pitch content, proof points, and decision trace."
    )
