"""Classify user ideas into adaptive project profiles for planning and validation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from agent.project_depth import ARCHETYPE_KEYWORDS, PROJECT_ARCHETYPES, classify_project_archetype

ProjectCategory = Literal[
    "browser_extension",
    "cli_tool",
    "portfolio_website",
    "multiplayer_game",
    "marketplace",
    "research_platform",
    "api_service",
    "sports_analytics",
    "web_app",
    "mobile_app",
    "desktop_app",
    "data_pipeline",
    "library",
    "ai_system",
]

ArchitectureType = Literal[
    "browser_extension",
    "cli",
    "static_site",
    "spa_with_api",
    "api_only",
    "game_client_server",
    "marketplace_platform",
    "research_workspace",
    "analytics_dashboard",
    "mobile_client_server",
    "desktop_app",
    "data_pipeline",
    "library_package",
    "ai_agent_platform",
]


@dataclass(frozen=True)
class ClassificationResult:
    """Public classification output for generation pipeline."""

    project_type: str
    complexity: str
    frontend_needed: bool
    backend_needed: bool
    database_needed: bool
    realtime_needed: bool
    ai_needed: bool
    deployment_strategy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectProfile:
    """Adaptive requirements derived from the user idea — not a fixed template."""

    category: ProjectCategory
    architecture_type: ArchitectureType
    project_archetype: str
    target_platform: str
    frontend_required: bool
    backend_required: bool
    database_required: bool
    realtime_required: bool
    ai_required: bool
    auth_required: bool
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATEGORY_PATTERNS: list[tuple[ProjectCategory, tuple[str, ...]]] = [
    ("browser_extension", ("browser extension", "chrome extension", "firefox extension", "content script", "manifest v3")),
    ("cli_tool", ("cli", "command line", "command-line", "terminal tool", "shell utility", "devtools")),
    ("portfolio_website", ("portfolio", "personal site", "landing page", "showcase website", "resume site")),
    ("multiplayer_game", ("multiplayer game", "real-time game", "online game", "game lobby", "matchmaking")),
    ("marketplace", ("marketplace", "buy and sell", "vendor", "listing platform", "two-sided market")),
    ("research_platform", ("research platform", "literature review", "citation", "lab notebook", "academic")),
    ("api_service", ("api only", "api-only", "rest api", "graphql api", "microservice", "webhook service")),
    ("sports_analytics", ("sports analytics", "player stats", "fantasy sports", "game film", "sports dashboard")),
    ("mobile_app", ("mobile app", "ios app", "android app", "react native", "expo")),
    ("desktop_app", ("desktop app", "electron", "tauri", "native desktop")),
    ("data_pipeline", ("etl", "data pipeline", "batch job", "stream processing", "data warehouse")),
    ("library", ("sdk", "library", "npm package", "pip package", "developer library")),
    ("ai_system", ("ai agent", "rag", "copilot", "llm", "embedding", "vector search")),
]


def _contains_term(text: str, term: str) -> bool:
    lowered = text.lower()
    token = term.lower().strip()
    if len(token) <= 4:
        return re.search(rf"\b{re.escape(token)}\b", lowered) is not None
    return token in lowered


def _mentions(text: str, *terms: str) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _category_from_signals(
    idea: str,
    *,
    intake: dict[str, Any] | None,
    requirements: dict[str, Any] | None,
) -> ProjectCategory:
    intake = intake or {}
    requirements = requirements or {}
    corpus = " ".join(
        [
            idea,
            str(intake.get("title") or ""),
            str(intake.get("techStackPreference") or intake.get("tech_stack_preference") or ""),
            str(requirements.get("target_platform") or intake.get("targetPlatform") or ""),
            " ".join(str(f) for f in (requirements.get("core_features") or [])),
        ]
    ).lower()

    platform = str(
        requirements.get("target_platform") or intake.get("targetPlatform") or ""
    ).lower()
    if platform in {"browser extension", "extension", "chrome extension"}:
        return "browser_extension"
    if platform in {"cli", "cli tool", "terminal", "command line"}:
        return "cli_tool"
    if platform in {"api", "api only", "api service", "backend only"}:
        return "api_service"

    for category, keywords in _CATEGORY_PATTERNS:
        if _mentions(corpus, *keywords):
            return category

    archetype = str(requirements.get("project_archetype") or classify_project_archetype(idea=idea))
    archetype_map: dict[str, ProjectCategory] = {
        "cli_tool": "cli_tool",
        "browser_extension": "browser_extension",
        "game": "multiplayer_game",
        "marketplace": "marketplace",
        "dashboard": "sports_analytics" if _mentions(idea, "sport", "athlete", "team") else "web_app",
        "library": "library",
        "data_pipeline": "data_pipeline",
        "ai_system": "ai_system",
        "content": "portfolio_website" if _mentions(idea, "portfolio", "personal") else "web_app",
    }
    return archetype_map.get(archetype, "web_app")


def _architecture_type(category: ProjectCategory) -> ArchitectureType:
    mapping: dict[ProjectCategory, ArchitectureType] = {
        "browser_extension": "browser_extension",
        "cli_tool": "cli",
        "portfolio_website": "static_site",
        "multiplayer_game": "game_client_server",
        "marketplace": "marketplace_platform",
        "research_platform": "research_workspace",
        "api_service": "api_only",
        "sports_analytics": "analytics_dashboard",
        "web_app": "spa_with_api",
        "mobile_app": "mobile_client_server",
        "desktop_app": "desktop_app",
        "data_pipeline": "data_pipeline",
        "library": "library_package",
        "ai_system": "ai_agent_platform",
    }
    return mapping[category]


def _target_platform(category: ProjectCategory, intake: dict[str, Any], requirements: dict[str, Any]) -> str:
    explicit = str(
        requirements.get("target_platform") or intake.get("targetPlatform") or ""
    ).strip()
    if explicit:
        return explicit
    defaults: dict[ProjectCategory, str] = {
        "browser_extension": "browser extension",
        "cli_tool": "cli tool",
        "portfolio_website": "web app",
        "api_service": "api",
        "multiplayer_game": "web app",
        "marketplace": "web app",
        "research_platform": "web app",
        "sports_analytics": "web app",
        "mobile_app": "mobile app",
        "desktop_app": "desktop app",
        "data_pipeline": "api",
        "library": "library",
        "ai_system": "ai agent",
        "web_app": "web app",
    }
    return defaults.get(category, "web app")


def _complexity_from_signals(
    idea: str,
    *,
    intake: dict[str, Any] | None,
    requirements: dict[str, Any] | None,
) -> str:
    requirements = requirements or {}
    intake = intake or {}
    depth = str(
        requirements.get("project_depth") or intake.get("projectDepth") or ""
    ).lower()
    if any(token in depth for token in ("production", "hackathon-winning", "advanced")):
        return "complex"
    if any(token in depth for token in ("simple", "minimal", "basic")):
        return "simple"
    word_count = len(re.findall(r"\w+", idea))
    feature_count = len(requirements.get("core_features") or requirements.get("must_have") or [])
    if word_count > 80 or feature_count >= 8:
        return "complex"
    if word_count < 25 and feature_count <= 3:
        return "simple"
    return "moderate"


def _deployment_strategy(category: ProjectCategory, profile_flags: ProjectProfile) -> str:
    if category == "cli_tool":
        return "PyPI or standalone binary distribution"
    if category == "browser_extension":
        return "Chrome Web Store / Firefox Add-ons packaging"
    if category == "portfolio_website":
        return "Static hosting (Netlify, Vercel, GitHub Pages)"
    if category == "api_service":
        return "Container or serverless API deployment"
    if category == "multiplayer_game":
        return "Realtime server + static client hosting"
    if category in {"sports_analytics", "marketplace", "research_platform", "web_app"}:
        if profile_flags.frontend_required and profile_flags.backend_required:
            return "Split frontend static hosting + managed API service"
        if profile_flags.frontend_required:
            return "Static or SPA hosting"
        return "Managed API service"
    if category == "library":
        return "Package registry publish (npm/PyPI)"
    if category == "data_pipeline":
        return "Scheduled job or stream worker deployment"
    return "Profile-appropriate managed deployment"


class ProjectClassifier:
    """Determine adaptive project requirements from idea and intake."""

    def classify(
        self,
        idea: str,
        *,
        intake: dict[str, Any] | None = None,
        requirements: dict[str, Any] | None = None,
    ) -> ProjectProfile:
        intake = intake or {}
        requirements = requirements or {}
        category = _category_from_signals(idea, intake=intake, requirements=requirements)
        architecture_type = _architecture_type(category)
        archetype = str(requirements.get("project_archetype") or classify_project_archetype(idea=idea))
        if archetype not in PROJECT_ARCHETYPES:
            archetype = "workflow"

        corpus = idea.lower()
        ai_required = bool(
            requirements.get("ai_required")
            or _mentions(corpus, "ai", "llm", "rag", "embedding", "copilot", "agent", "gemini", "openai")
        )
        realtime_required = bool(
            requirements.get("realtime_required")
            or category == "multiplayer_game"
            or _mentions(corpus, "realtime", "real-time", "websocket", "live", "multiplayer", "sync")
        )
        frontend_required = category not in {
            "cli_tool",
            "api_service",
            "library",
            "data_pipeline",
        }
        backend_required = category not in {"portfolio_website"} or ai_required
        if category == "portfolio_website" and not _mentions(corpus, "api", "backend", "server"):
            backend_required = False

        database_required = bool(requirements.get("database_required"))
        if requirements.get("database_required") is None:
            database_required = category in {
                "marketplace",
                "multiplayer_game",
                "research_platform",
                "sports_analytics",
                "web_app",
                "mobile_app",
                "ai_system",
            } and category not in {"portfolio_website", "browser_extension", "cli_tool", "library"}

        auth_required = bool(requirements.get("auth_required"))
        if requirements.get("auth_required") is None:
            auth_required = category in {
                "marketplace",
                "multiplayer_game",
                "research_platform",
                "sports_analytics",
                "web_app",
                "mobile_app",
                "ai_system",
            }

        rationale = [
            f"category={category} from idea/platform signals",
            f"architecture_type={architecture_type}",
            f"archetype={archetype}",
        ]
        if ai_required:
            rationale.append("AI/LLM signals detected")
        if realtime_required:
            rationale.append("Realtime/multiplayer signals detected")

        return ProjectProfile(
            category=category,
            architecture_type=architecture_type,
            project_archetype=archetype,
            target_platform=_target_platform(category, intake, requirements),
            frontend_required=frontend_required,
            backend_required=backend_required,
            database_required=database_required,
            realtime_required=realtime_required,
            ai_required=ai_required,
            auth_required=auth_required,
            rationale=rationale,
        )

    def classify_for_generation(
        self,
        idea: str,
        *,
        intake: dict[str, Any] | None = None,
        requirements: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        profile = self.classify(idea, intake=intake, requirements=requirements)
        return ClassificationResult(
            project_type=profile.category,
            complexity=_complexity_from_signals(idea, intake=intake, requirements=requirements),
            frontend_needed=profile.frontend_required,
            backend_needed=profile.backend_required,
            database_needed=profile.database_required,
            realtime_needed=profile.realtime_required,
            ai_needed=profile.ai_required,
            deployment_strategy=_deployment_strategy(profile.category, profile),
        )


def classify_project(
    idea: str,
    *,
    intake: dict[str, Any] | None = None,
    requirements: dict[str, Any] | None = None,
) -> ProjectProfile:
    return ProjectClassifier().classify(idea, intake=intake, requirements=requirements)


def classify_for_generation(
    idea: str,
    *,
    intake: dict[str, Any] | None = None,
    requirements: dict[str, Any] | None = None,
) -> ClassificationResult:
    return ProjectClassifier().classify_for_generation(
        idea, intake=intake, requirements=requirements
    )


def apply_profile_to_requirements(
    requirements: dict[str, Any],
    profile: ProjectProfile,
) -> dict[str, Any]:
    """Merge classifier output into workflow requirements without forcing web defaults."""
    updated = dict(requirements)
    updated["project_archetype"] = profile.project_archetype
    updated["target_platform"] = profile.target_platform
    updated["project_category"] = profile.category
    updated["architecture_type"] = profile.architecture_type
    updated["frontend_required"] = profile.frontend_required
    updated["backend_required"] = profile.backend_required
    updated["database_required"] = profile.database_required
    updated["realtime_required"] = profile.realtime_required
    updated["ai_required"] = profile.ai_required
    updated["auth_required"] = profile.auth_required
    updated["project_profile"] = profile.to_dict()

    routes = [
        str(route).strip()
        for route in (updated.get("api_routes") or [])
        if str(route).strip()
    ]
    if profile.category in {"cli_tool", "browser_extension", "portfolio_website", "library", "data_pipeline"}:
        routes = []
    elif not profile.backend_required:
        routes = []
    elif routes and not profile.auth_required:
        routes = [route for route in routes if "/auth/" not in route.lower()]
    if routes and not profile.database_required:
        routes = [route for route in routes if "/dashboard" not in route.lower()]
    updated["api_routes"] = routes

    advanced = [
        str(item).strip()
        for item in (updated.get("advanced_features") or [])
        if str(item).strip()
    ]
    if advanced:
        if not profile.auth_required:
            advanced = [
                item for item in advanced if "auth" not in item.lower()
            ]
        if not profile.frontend_required:
            advanced = [
                item
                for item in advanced
                if "dashboard" not in item.lower() and "workspace" not in item.lower()
            ]
        updated["advanced_features"] = advanced

    criteria = [
        str(item).strip()
        for item in (updated.get("success_criteria") or [])
        if str(item).strip()
    ]
    if criteria:
        if not profile.frontend_required and not profile.backend_required:
            criteria = [
                item
                for item in criteria
                if "frontend" not in item.lower() and "backend" not in item.lower()
            ]
        elif not profile.database_required:
            criteria = [item for item in criteria if "data model" not in item.lower()]
        updated["success_criteria"] = criteria or list(updated.get("success_criteria") or [])

    return updated
