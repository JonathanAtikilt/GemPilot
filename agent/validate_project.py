"""Validate generated repositories against a ProjectPlan — not a fixed template."""

from __future__ import annotations

from typing import Any

from agent.architecture_planner import ArchitecturePlan, plan_architecture
from agent.generation_logging import log_validation
from agent.project_classifier import ProjectProfile, classify_project
from agent.project_plan import ProjectPlan, build_project_plan
from agent.project_validation import validate_project_output
from agent.idea_context import project_title_from_context
from agent.project_validation import (
    _artifact_content,
    _artifact_map,
    _idea_tokens,
    _imports_resolve,
    _text_reflects_idea,
    _title_matches_idea,
)

_TEMPLATE_ONLY_CHECKS = frozenset(
    {
        "studypilot_benchmark_complete",
        "ui_specific",
        "frontend_routes_or_pages_exist",
        "backend_routes_exist",
        "database_models_used",
        "api_and_database_planned",
        "architecture_documents_full_system",
        "seed_data_present",
        "implementation_files_complete",
    }
)


def _resolve_plan(
    *,
    idea: str,
    intake: dict[str, Any] | None,
    project_plan: ProjectPlan | dict[str, Any] | None,
    project_requirements: dict[str, Any] | None,
    architecture_plan: dict[str, Any] | None,
    recommended_stack: dict[str, Any] | None = None,
) -> ProjectPlan:
    if isinstance(project_plan, ProjectPlan):
        return project_plan
    scope = project_requirements or (project_plan if isinstance(project_plan, dict) else {}) or {}
    return build_project_plan(
        idea=idea,
        intake=intake,
        scope=scope,
        recommended_stack=recommended_stack or scope.get("chosen_stack"),
        existing_repo_plan=architecture_plan or scope,
    )


def _filter_legacy_checks(
    validation: dict[str, Any],
    profile: ProjectProfile,
    arch_plan: ArchitecturePlan,
    *,
    plan: ProjectPlan | None = None,
    project_requirements: dict[str, Any] | None = None,
    require_live_manifest: bool = False,
) -> dict[str, Any]:
    vp = arch_plan.validation_profile
    checks = []
    for item in validation.get("checks") or []:
        name = str(item.get("name") or "")
        if name == "studypilot_benchmark_complete":
            continue
        if name in {"ui_specific", "frontend_routes_or_pages_exist"} and not vp.get(
            "check_frontend_routes", profile.frontend_required
        ):
            checks.append({**item, "passed": True, "detail": "Skipped — no frontend required for this profile."})
            continue
        if name in {"backend_routes_exist", "database_models_used"} and not vp.get(
            "check_backend_routes", profile.backend_required
        ):
            checks.append({**item, "passed": True, "detail": "Skipped — no web backend required for this profile."})
            continue
        if name == "seed_data_present" and not vp.get("check_seed_data", profile.database_required):
            checks.append({**item, "passed": True, "detail": "Skipped — seed data not required for this profile."})
            continue
        if name == "architecture_documents_full_system" and profile.category in {
            "cli_tool",
            "browser_extension",
            "portfolio_website",
            "api_service",
        }:
            checks.append({**item, "passed": True, "detail": "Skipped — simplified architecture doc expected."})
            continue
        if name == "api_and_database_planned" and not profile.database_required:
            checks.append({**item, "passed": True, "detail": "Skipped — database not required for this profile."})
            continue
        if name == "auth_data_flow_present" and not profile.auth_required:
            checks.append({**item, "passed": True, "detail": "Skipped — authentication not required for this profile."})
            continue
        if name == "implementation_files_complete" and profile.category in {
            "cli_tool",
            "browser_extension",
            "portfolio_website",
        }:
            checks.append({**item, "passed": True, "detail": "Skipped — non-web implementation layout."})
            continue
        if plan and name == "requirements_expanded":
            checks.append(
                {
                    **item,
                    "passed": True,
                    "detail": "Validated against explicit ProjectPlan features (no template stuffing).",
                }
            )
            continue
        if plan and name == "advanced_features_present":
            checks.append(
                {
                    **item,
                    "passed": True,
                    "detail": "Skipped — advanced features only when explicitly planned.",
                }
            )
            continue
        if plan and name == "user_flow_defined":
            has_flows = bool(plan.workflows) or bool(
                (project_requirements or {}).get("user_flows")
            )
            if has_flows:
                checks.append(
                    {
                        **item,
                        "passed": True,
                        "detail": "Validated against ProjectPlan workflows.",
                    }
                )
                continue
        checks.append(item)

    still_critical = {
        "title_matches_idea",
        "readme_specific",
        "requirements_expanded",
        "no_generic_fallback_features",
        "generated_files_not_placeholders",
        "imports_resolve",
        "readme_setup_features_demo",
        "demo_materials_generated",
        "user_flow_defined",
        "testing_and_deployment_present",
    }
    if profile.frontend_required and vp.get("check_frontend_routes"):
        still_critical.add("ui_specific")
    if profile.backend_required and vp.get("check_backend_routes"):
        still_critical.update({"backend_routes_exist"})
    if profile.database_required and vp.get("check_database_models"):
        still_critical.update({"database_models_used", "seed_data_present"})
    if require_live_manifest:
        still_critical.add("live_manifest_only")

    passed = all(
        item.get("passed") for item in checks if str(item.get("name") or "") in still_critical
    )
    warnings = [str(item.get("detail") or "") for item in checks if not item.get("passed")]
    return {**validation, "passed": passed, "checks": checks, "warnings": warnings}


def _plan_checks(
    *,
    plan: ProjectPlan,
    generated_artifacts: list[dict[str, Any]],
    idea: str,
    intake: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    files = _artifact_map(generated_artifacts)
    readme = _artifact_content(generated_artifacts, "README.md")
    title = project_title_from_context(idea=idea, intake=intake or {})
    tokens = _idea_tokens(idea)
    rules = plan.validation_rules
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    add(
        "plan_imports",
        (not rules.get("check_imports", True)) or _imports_resolve(files),
        "Imports resolve within the generated repository.",
    )
    add(
        "plan_runtime",
        _runtime_entrypoints_present(files, plan),
        "Runtime entrypoints from the architecture plan should exist.",
    )
    add(
        "plan_readme_accuracy",
        bool(readme) and _text_reflects_idea(readme, tokens) and _title_matches_idea(title, idea, tokens, _idea_tokens(title)),
        "README should accurately describe the submitted idea.",
    )
    add(
        "plan_feature_completeness",
        _features_reflected(readme, plan, tokens),
        "Required plan features should appear in README without excluded template features.",
    )
    if plan.profile.backend_required:
        add(
            "plan_apis",
            _api_surface_present(files, plan)
            or any(
                path in files for path in ("backend/main.py", "src/lib/api.js", "docs/API_SPEC.md")
            ),
            "Backend/API surface should exist when the plan requires it.",
        )
    if rules.get("check_workflows") and plan.workflows:
        add(
            "plan_workflows",
            _workflows_supported(files, plan, tokens),
            "Generated project should support planned user workflows.",
        )
    return checks


def validate_project(
    *,
    idea: str,
    intake: dict[str, Any] | None,
    project_plan: ProjectPlan | dict[str, Any] | None = None,
    generated_artifacts: list[dict[str, Any]],
    model_modes: list[str] | None = None,
    project_requirements: dict[str, Any] | None = None,
    architecture_plan: dict[str, Any] | None = None,
    require_live_manifest: bool = False,
    manifest_model_mode: str | None = None,
    allow_degraded_manifest: bool = False,
) -> dict[str, Any]:
    """Validate output against ProjectPlan plus profile-aware legacy checks."""
    plan = _resolve_plan(
        idea=idea,
        intake=intake,
        project_plan=project_plan,
        project_requirements=project_requirements,
        architecture_plan=architecture_plan,
    )
    merged_requirements = dict(project_requirements or {})
    if isinstance(project_plan, dict):
        merged_requirements.update(project_plan)
    merged_requirements.setdefault("target_platform", plan.profile.target_platform)
    merged_requirements.setdefault("project_archetype", plan.profile.project_archetype)
    merged_requirements.setdefault("core_features", plan.required_features)

    legacy = validate_project_output(
        idea=idea,
        intake=intake,
        project_requirements=merged_requirements,
        architecture_plan=architecture_plan or {"file_tree": plan.file_tree},
        generated_artifacts=generated_artifacts,
        model_modes=model_modes or [],
        require_live_manifest=require_live_manifest,
        manifest_model_mode=manifest_model_mode,
        allow_degraded_manifest=allow_degraded_manifest,
    )
    filtered = _filter_legacy_checks(
        legacy,
        plan.profile,
        plan.architecture,
        plan=plan,
        require_live_manifest=require_live_manifest,
        project_requirements=merged_requirements,
    )
    plan_checks = _plan_checks(
        plan=plan,
        generated_artifacts=generated_artifacts,
        idea=idea,
        intake=intake,
    )
    checks = filtered["checks"] + plan_checks
    plan_critical = {
        "plan_imports",
        "plan_readme_accuracy",
        "plan_feature_completeness",
    }
    passed = filtered["passed"] and all(
        check["passed"] for check in plan_checks if check["name"] in plan_critical
    )
    failed = [c["detail"] for c in checks if not c.get("passed")]
    log_validation(passed=passed, project_type=plan.classification.project_type, failed_checks=failed)

    return {
        **filtered,
        "passed": passed,
        "checks": checks,
        "project_title": filtered.get("project_title") or project_title_from_context(idea=idea, intake=intake or {}),
        "project_type": plan.classification.project_type,
        "project_category": plan.profile.category,
        "architecture_type": plan.profile.architecture_type,
        "validation_profile": plan.validation_rules,
        "project_plan": plan.to_dict(),
    }


def _runtime_entrypoints_present(files: dict[str, str], plan: ProjectPlan) -> bool:
    entrypoints = plan.architecture.entrypoints or []
    if not entrypoints:
        return bool(files)
    hits = sum(1 for path in entrypoints if path in files)
    if hits >= max(1, len(entrypoints) // 2):
        return True
    common = (
        "src/App.jsx",
        "src/main.jsx",
        "backend/main.py",
        "cli/main.py",
        "frontend/index.html",
        "frontend/src/main.jsx",
    )
    return any(path in files for path in common)


def _api_surface_present(files: dict[str, str], plan: ProjectPlan) -> bool:
    backend_paths = plan.architecture.backend_paths
    if backend_paths:
        return any(path in files for path in backend_paths)
    return any(path.endswith(("main.py", "index.js", "server.js")) for path in files)


def _workflows_supported(files: dict[str, str], plan: ProjectPlan, tokens: set[str]) -> bool:
    combined = "\n".join(files.values()).lower()
    screens = {
        str(step.get("screen") or "").lower()
        for step in plan.workflows
        if isinstance(step, dict)
    }
    screen_hits = sum(1 for screen in screens if screen and screen in combined)
    token_hits = sum(1 for token in tokens if token in combined)
    return screen_hits >= 1 or token_hits >= min(2, len(tokens))


def _features_reflected(readme: str, plan: ProjectPlan, tokens: set[str]) -> bool:
    if not plan.required_features:
        return bool(readme) and _text_reflects_idea(readme, tokens)
    lowered = readme.lower()
    hits = sum(1 for feature in plan.required_features if feature.lower()[:24] in lowered)
    excluded_hits = sum(
        1 for feature in plan.excluded_features if feature.lower()[:24] in lowered
    )
    required_ratio = hits / max(len(plan.required_features), 1)
    return bool(readme) and (required_ratio >= 0.34 or _text_reflects_idea(readme, tokens)) and excluded_hits == 0


validate_project_adaptive = validate_project
validate_mvp = validate_project
