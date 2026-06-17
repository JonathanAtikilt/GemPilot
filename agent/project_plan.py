"""Unified project plan composed from classification, architecture, and scope."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from agent.architecture_planner import ArchitecturePlan, plan_architecture
from agent.project_classifier import (
    ClassificationResult,
    ProjectProfile,
    classify_for_generation,
    classify_project,
)


@dataclass
class ProjectPlan:
    """Single source of truth for generation and validation."""

    project_summary: str
    target_users: str
    chosen_stack: dict[str, str]
    required_features: list[str]
    excluded_features: list[str]
    data_models: list[str]
    api_routes: list[str]
    workflows: list[dict[str, Any]]
    validation_rules: dict[str, bool]
    classification: ClassificationResult
    profile: ProjectProfile
    architecture: ArchitecturePlan
    file_tree: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["classification"] = self.classification.to_dict()
        payload["profile"] = self.profile.to_dict()
        payload["architecture"] = self.architecture.to_dict()
        return payload


def _infer_excluded_features(
    *,
    idea: str,
    profile: ProjectProfile,
    required: list[str],
) -> list[str]:
    """Features commonly stuffed but not requested or logically required."""
    excluded: list[str] = []
    corpus = idea.lower()
    required_corpus = " ".join(required).lower()

    if not profile.frontend_required:
        excluded.extend(["React dashboard", "SPA frontend", "Authenticated web workspace"])
    if not profile.backend_required:
        excluded.extend(["FastAPI backend", "REST API layer", "Microservice backend"])
    if not profile.database_required:
        excluded.extend(["PostgreSQL schema", "Seed data loader", "ORM models"])
    if not profile.auth_required:
        excluded.extend(["User authentication", "Login/register flow", "JWT auth"])
    if not profile.ai_required and "ai" not in corpus and "llm" not in corpus:
        excluded.extend(["LLM integration", "RAG pipeline", "AI copilot"])
    if "dashboard" not in corpus and "dashboard" not in required_corpus:
        excluded.append("Generic operational dashboard")
    if "marketplace" not in corpus and profile.category != "marketplace":
        excluded.append("Two-sided marketplace listings")
    return _unique(excluded)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


def build_project_plan(
    *,
    idea: str,
    intake: dict[str, Any] | None = None,
    scope: dict[str, Any] | None = None,
    recommended_stack: dict[str, Any] | None = None,
    existing_repo_plan: dict[str, Any] | None = None,
) -> ProjectPlan:
    """Compose a ProjectPlan from classifier output, scope, stack, and architecture."""
    intake = intake or {}
    scope = scope or {}
    classification = classify_for_generation(idea, intake=intake, requirements=scope)
    profile = classify_project(idea, intake=intake, requirements=scope)
    architecture = plan_architecture(
        profile,
        idea=idea,
        recommended_stack=recommended_stack,
        requirements=scope,
        existing_plan=existing_repo_plan,
    )

    required = _unique(
        [
            str(item).strip()
            for item in (
                scope.get("core_features")
                or scope.get("must_have")
                or intake.get("requiredFeatures")
                or []
            )
            if str(item).strip()
        ]
    )
    excluded = _infer_excluded_features(idea=idea, profile=profile, required=required)

    stack = {
        "frontend": str((recommended_stack or {}).get("frontend") or ""),
        "backend": str((recommended_stack or {}).get("backend") or ""),
        "database": str((recommended_stack or {}).get("database") or ""),
        "deployment": str((recommended_stack or {}).get("deployment") or ""),
        "testing": str((recommended_stack or {}).get("testing") or ""),
    }
    if not any(stack.values()):
        stack = _default_stack(profile, classification.deployment_strategy)

    data_models = _unique(
        [
            str(item).strip()
            for item in (scope.get("data_entities") or architecture.database_paths or [])
            if str(item).strip()
        ]
    )
    api_routes = _unique(
        [
            str(item).strip()
            for item in (scope.get("api_routes") or [])
            if str(item).strip()
        ]
    )
    workflows = (
        scope.get("user_flows")
        or scope.get("workflows")
        or scope.get("demo_path")
        or []
    )
    if not isinstance(workflows, list):
        workflows = []
    if not workflows and scope.get("core_features"):
        workflows = [
            {
                "step": "1",
                "screen": "Start",
                "action": str(scope["core_features"][0]),
                "api": None,
            }
        ]

    summary = str(scope.get("project_boundary") or scope.get("project_summary") or idea).strip()
    target_users = str(
        scope.get("target_users")
        or intake.get("targetUsers")
        or "Users described in the submitted project idea"
    )

    validation_rules = dict(architecture.validation_profile)
    validation_rules.setdefault("check_imports", True)
    validation_rules.setdefault("check_readme_accuracy", True)
    validation_rules.setdefault("check_feature_completeness", True)
    validation_rules.setdefault("check_workflows", bool(workflows))

    return ProjectPlan(
        project_summary=summary,
        target_users=target_users,
        chosen_stack=stack,
        required_features=required,
        excluded_features=excluded,
        data_models=data_models,
        api_routes=api_routes,
        workflows=[dict(step) for step in workflows if isinstance(step, dict)],
        validation_rules=validation_rules,
        classification=classification,
        profile=profile,
        architecture=architecture,
        file_tree=list(architecture.file_tree),
    )


def _default_stack(profile: ProjectProfile, deployment_strategy: str) -> dict[str, str]:
    if profile.category == "cli_tool":
        return {
            "frontend": "",
            "backend": "Python CLI",
            "database": "",
            "deployment": deployment_strategy,
            "testing": "pytest",
        }
    if profile.category == "browser_extension":
        return {
            "frontend": "Extension popup/options UI",
            "backend": "",
            "database": "browser storage",
            "deployment": deployment_strategy,
            "testing": "manual + unit tests",
        }
    if profile.category == "api_service":
        return {
            "frontend": "",
            "backend": "FastAPI or Express",
            "database": "PostgreSQL when persistence required",
            "deployment": deployment_strategy,
            "testing": "pytest or vitest",
        }
    if profile.category == "portfolio_website":
        return {
            "frontend": "Static HTML/CSS/JS",
            "backend": "",
            "database": "",
            "deployment": deployment_strategy,
            "testing": "smoke tests",
        }
    return {
        "frontend": "React or Next.js when UI required",
        "backend": "FastAPI or Node when API required",
        "database": "PostgreSQL when persistence required",
        "deployment": deployment_strategy,
        "testing": "pytest + frontend tests",
    }
