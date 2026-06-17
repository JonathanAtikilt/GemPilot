"""Dynamic repository structure planning based on project profile — not a fixed template."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from agent.project_classifier import ProjectProfile

# Core docs every generated repo should include.
CORE_UNIVERSAL_PATHS: frozenset[str] = frozenset(
    {
        "README.md",
        "docs/PROJECT_PLAN.md",
        "docs/ARCHITECTURE.md",
        "docs/DEPLOY.md",
        "docs/TESTING_STRATEGY.md",
    }
)

# Optional hackathon/demo artifacts — only when is_hackathon_mode=True.
HACKATHON_PATHS: frozenset[str] = frozenset(
    {
        "demo/script.md",
        "demo/storyboard.md",
        "demo/demo_walkthrough.md",
        "demo/video_outline.md",
        "demo/voiceover.md",
        "demo/demo_script.md",
        "docs/HACKATHON_SUBMISSION.md",
    }
)

# Backward-compatible alias.
UNIVERSAL_PATHS: frozenset[str] = CORE_UNIVERSAL_PATHS | HACKATHON_PATHS

GAP_FILL_PATHS: frozenset[str] = CORE_UNIVERSAL_PATHS | frozenset(
    {
        "docs/API_SPEC.md",
        "docs/KNOWN_LIMITATIONS.md",
        ".env.example",
    }
)


@dataclass
class ArchitecturePlan:
    """Planned repository shape and generation stages."""

    file_tree: list[str]
    implementation_stages: list[str]
    frontend_paths: list[str] = field(default_factory=list)
    backend_paths: list[str] = field(default_factory=list)
    database_paths: list[str] = field(default_factory=list)
    test_paths: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    validation_profile: dict[str, bool] = field(default_factory=dict)
    architecture_overview: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _blueprint_paths(profile: ProjectProfile) -> ArchitecturePlan:
    """Return a category-specific file tree — not the default React+FastAPI layout."""
    category = profile.category
    rationale = [f"Blueprint for category={category}", f"architecture_type={profile.architecture_type}"]

    if category == "browser_extension":
        return ArchitecturePlan(
            file_tree=[
                "README.md",
                "manifest.json",
                "background/service_worker.js",
                "background/messaging.js",
                "content/content_script.js",
                "content/dom_utils.js",
                "popup/popup.html",
                "popup/popup.js",
                "popup/popup.css",
                "popup/options.html",
                "popup/options.js",
                "shared/storage.js",
                "icons/icon-16.png",
                "docs/ARCHITECTURE.md",
                "docs/DEPLOY.md",
                "docs/PROJECT_PLAN.md",
                "docs/TESTING_STRATEGY.md",
                "demo/script.md",
                "demo/storyboard.md",
                "demo/demo_walkthrough.md",
                "demo/video_outline.md",
            ],
            implementation_stages=["extension_core", "popup_ui", "content_scripts", "docs", "demo"],
            frontend_paths=["popup/popup.html", "popup/popup.js", "popup/options.html"],
            backend_paths=["background/service_worker.js", "content/content_script.js"],
            database_paths=[],
            test_paths=[],
            entrypoints=["background/service_worker.js", "popup/popup.js", "content/content_script.js"],
            validation_profile={
                "check_imports": True,
                "check_frontend_routes": False,
                "check_backend_routes": False,
                "check_database_models": False,
                "check_auth_flow": False,
                "check_seed_data": False,
                "check_demo_materials": True,
            },
            architecture_overview=[
                "Browser extension with manifest, background service worker, and content scripts.",
                "Popup/options UI for user controls; no traditional web server required.",
            ],
            rationale=rationale,
        )

    if category == "cli_tool":
        return ArchitecturePlan(
            file_tree=[
                "README.md",
                "pyproject.toml",
                "requirements.txt",
                "cli/__init__.py",
                "cli/main.py",
                "commands/__init__.py",
                "commands/run.py",
                "commands/config.py",
                "utils/__init__.py",
                "utils/parser.py",
                "utils/formatters.py",
                "tests/test_cli.py",
                "tests/test_commands.py",
                "data/sample_input.json",
                "docs/ARCHITECTURE.md",
                "docs/DEPLOY.md",
                "docs/PROJECT_PLAN.md",
                "docs/TESTING_STRATEGY.md",
                "demo/script.md",
                "demo/storyboard.md",
                "demo/demo_walkthrough.md",
                "demo/video_outline.md",
            ],
            implementation_stages=["cli_core", "commands", "tests", "docs", "demo"],
            frontend_paths=[],
            backend_paths=["cli/main.py", "commands/run.py", "utils/parser.py"],
            database_paths=[],
            test_paths=["tests/test_cli.py", "tests/test_commands.py"],
            entrypoints=["cli/main.py"],
            validation_profile={
                "check_imports": True,
                "check_frontend_routes": False,
                "check_backend_routes": False,
                "check_database_models": False,
                "check_auth_flow": False,
                "check_seed_data": False,
                "check_demo_materials": True,
            },
            architecture_overview=[
                "Python CLI package with command modules and a testable core library.",
                "No web frontend or HTTP API layer.",
            ],
            rationale=rationale,
        )

    if category == "portfolio_website":
        return ArchitecturePlan(
            file_tree=[
                "README.md",
                "frontend/index.html",
                "frontend/src/main.js",
                "frontend/src/styles.css",
                "frontend/src/sections/hero.js",
                "frontend/src/sections/projects.js",
                "frontend/src/sections/contact.js",
                "frontend/public/assets/resume.pdf",
                "docs/ARCHITECTURE.md",
                "docs/DEPLOY.md",
                "docs/PROJECT_PLAN.md",
                "docs/TESTING_STRATEGY.md",
                "demo/script.md",
                "demo/storyboard.md",
                "demo/demo_walkthrough.md",
                "demo/video_outline.md",
            ],
            implementation_stages=["static_site", "content_sections", "docs", "demo"],
            frontend_paths=["frontend/index.html", "frontend/src/main.js", "frontend/src/sections/hero.js"],
            backend_paths=[],
            database_paths=[],
            test_paths=[],
            entrypoints=["frontend/index.html", "frontend/src/main.js"],
            validation_profile={
                "check_imports": True,
                "check_frontend_routes": False,
                "check_backend_routes": False,
                "check_database_models": False,
                "check_auth_flow": False,
                "check_seed_data": False,
                "check_demo_materials": True,
            },
            architecture_overview=[
                "Static portfolio site with section-based content modules.",
                "Deployable to static hosting without a backend.",
            ],
            rationale=rationale,
        )

    if category == "multiplayer_game":
        return ArchitecturePlan(
            file_tree=[
                "README.md",
                "package.json",
                "client/index.html",
                "client/src/main.js",
                "client/src/game/GameCanvas.js",
                "client/src/game/Input.js",
                "client/src/net/socket.js",
                "server/index.js",
                "server/rooms.js",
                "server/gameState.js",
                "shared/protocol.js",
                "tests/server.test.js",
                "docs/ARCHITECTURE.md",
                "docs/API_SPEC.md",
                "docs/DEPLOY.md",
                "docs/PROJECT_PLAN.md",
                "docs/TESTING_STRATEGY.md",
                "demo/script.md",
                "demo/storyboard.md",
                "demo/demo_walkthrough.md",
                "demo/video_outline.md",
            ],
            implementation_stages=["shared_protocol", "game_server", "game_client", "tests", "docs", "demo"],
            frontend_paths=["client/index.html", "client/src/main.js", "client/src/game/GameCanvas.js"],
            backend_paths=["server/index.js", "server/rooms.js", "server/gameState.js"],
            database_paths=[],
            test_paths=["tests/server.test.js"],
            entrypoints=["client/src/main.js", "server/index.js"],
            validation_profile={
                "check_imports": True,
                "check_frontend_routes": False,
                "check_backend_routes": True,
                "check_database_models": False,
                "check_auth_flow": False,
                "check_realtime": True,
                "check_demo_materials": True,
            },
            architecture_overview=[
                "Realtime multiplayer client/server game with shared protocol module.",
                "WebSocket or socket.io style room management.",
            ],
            rationale=rationale + ["realtime_required"],
        )

    if category == "marketplace":
        return ArchitecturePlan(
            file_tree=[
                "README.md",
                "package.json",
                "frontend/src/main.jsx",
                "frontend/src/App.jsx",
                "frontend/src/pages/Listings.jsx",
                "frontend/src/pages/ListingDetail.jsx",
                "frontend/src/pages/SellerDashboard.jsx",
                "frontend/src/lib/api.js",
                "backend/main.py",
                "backend/models.py",
                "backend/routes/listings.py",
                "backend/routes/orders.py",
                "backend/db.py",
                "docs/DATABASE_SCHEMA.sql",
                "data/seed.json",
                "scripts/seed_data.py",
                "tests/test_marketplace_api.py",
                "docs/ARCHITECTURE.md",
                "docs/API_SPEC.md",
                "docs/DEPLOY.md",
                "docs/PROJECT_PLAN.md",
                "docs/TESTING_STRATEGY.md",
                "demo/script.md",
                "demo/storyboard.md",
                "demo/demo_walkthrough.md",
                "demo/video_outline.md",
            ],
            implementation_stages=["database", "backend", "frontend", "tests", "docs", "demo"],
            frontend_paths=["frontend/src/App.jsx", "frontend/src/pages/Listings.jsx"],
            backend_paths=["backend/main.py", "backend/routes/listings.py", "backend/routes/orders.py"],
            database_paths=["backend/models.py", "docs/DATABASE_SCHEMA.sql"],
            test_paths=["tests/test_marketplace_api.py"],
            entrypoints=["frontend/src/main.jsx", "backend/main.py"],
            validation_profile={
                "check_imports": True,
                "check_frontend_routes": True,
                "check_backend_routes": True,
                "check_database_models": True,
                "check_auth_flow": True,
                "check_seed_data": True,
                "check_demo_materials": True,
            },
            architecture_overview=[
                "Two-sided marketplace with listings, orders, and seller workflows.",
                "Separate listing and order API surfaces.",
            ],
            rationale=rationale,
        )

    if category == "research_platform":
        return ArchitecturePlan(
            file_tree=[
                "README.md",
                "package.json",
                "client/src/main.jsx",
                "client/src/App.jsx",
                "client/src/pages/Library.jsx",
                "client/src/pages/Workspace.jsx",
                "client/src/pages/Citations.jsx",
                "client/src/lib/api.js",
                "server/main.py",
                "server/models.py",
                "server/routes/papers.py",
                "server/routes/notes.py",
                "server/services/search.py",
                "server/db.py",
                "docs/DATABASE_SCHEMA.sql",
                "data/seed.json",
                "tests/test_research_api.py",
                "docs/ARCHITECTURE.md",
                "docs/API_SPEC.md",
                "docs/DEPLOY.md",
                "docs/PROJECT_PLAN.md",
                "docs/TESTING_STRATEGY.md",
                "demo/script.md",
                "demo/storyboard.md",
                "demo/demo_walkthrough.md",
                "demo/video_outline.md",
            ],
            implementation_stages=["database", "backend", "search", "frontend", "tests", "docs", "demo"],
            frontend_paths=["client/src/App.jsx", "client/src/pages/Library.jsx", "client/src/pages/Workspace.jsx"],
            backend_paths=["server/main.py", "server/routes/papers.py", "server/services/search.py"],
            database_paths=["server/models.py", "docs/DATABASE_SCHEMA.sql"],
            test_paths=["tests/test_research_api.py"],
            entrypoints=["client/src/main.jsx", "server/main.py"],
            validation_profile={
                "check_imports": True,
                "check_frontend_routes": True,
                "check_backend_routes": True,
                "check_database_models": True,
                "check_auth_flow": True,
                "check_ai_features": profile.ai_required,
                "check_demo_materials": True,
            },
            architecture_overview=[
                "Research workspace with paper library, notes, and citation tooling.",
                "Search/index service for literature discovery.",
            ],
            rationale=rationale,
        )

    if category == "api_service":
        return ArchitecturePlan(
            file_tree=[
                "README.md",
                "requirements.txt",
                "pyproject.toml",
                "backend/__init__.py",
                "backend/main.py",
                "backend/routes/__init__.py",
                "backend/routes/health.py",
                "backend/routes/v1.py",
                "backend/models.py",
                "backend/services.py",
                "backend/db.py",
                "tests/test_api.py",
                "docs/ARCHITECTURE.md",
                "docs/API_SPEC.md",
                "docs/DEPLOY.md",
                "docs/PROJECT_PLAN.md",
                "docs/TESTING_STRATEGY.md",
                "demo/script.md",
                "demo/storyboard.md",
                "demo/demo_walkthrough.md",
                "demo/video_outline.md",
            ],
            implementation_stages=["api_core", "routes", "tests", "docs", "demo"],
            frontend_paths=[],
            backend_paths=["backend/main.py", "backend/routes/v1.py", "backend/services.py"],
            database_paths=["backend/models.py", "backend/db.py"],
            test_paths=["tests/test_api.py"],
            entrypoints=["backend/main.py"],
            validation_profile={
                "check_imports": True,
                "check_frontend_routes": False,
                "check_backend_routes": True,
                "check_database_models": profile.database_required,
                "check_auth_flow": profile.auth_required,
                "check_seed_data": False,
                "check_demo_materials": True,
            },
            architecture_overview=[
                "API-only service with versioned HTTP routes and OpenAPI-ready layout.",
                "No SPA frontend required.",
            ],
            rationale=rationale,
        )

    if category == "sports_analytics":
        return ArchitecturePlan(
            file_tree=[
                "README.md",
                "package.json",
                "frontend/src/main.jsx",
                "frontend/src/App.jsx",
                "frontend/src/pages/TeamDashboard.jsx",
                "frontend/src/pages/PlayerStats.jsx",
                "frontend/src/pages/GameFilm.jsx",
                "frontend/src/components/StatChart.jsx",
                "frontend/src/lib/api.js",
                "backend/main.py",
                "backend/models.py",
                "backend/routes/teams.py",
                "backend/routes/players.py",
                "backend/routes/games.py",
                "backend/db.py",
                "data/seed.json",
                "scripts/seed_data.py",
                "tests/test_analytics_api.py",
                "docs/ARCHITECTURE.md",
                "docs/API_SPEC.md",
                "docs/DATABASE_SCHEMA.sql",
                "docs/DEPLOY.md",
                "docs/PROJECT_PLAN.md",
                "docs/TESTING_STRATEGY.md",
                "demo/script.md",
                "demo/storyboard.md",
                "demo/demo_walkthrough.md",
                "demo/video_outline.md",
            ],
            implementation_stages=["database", "backend", "analytics_api", "frontend", "tests", "docs", "demo"],
            frontend_paths=["frontend/src/App.jsx", "frontend/src/pages/TeamDashboard.jsx"],
            backend_paths=["backend/main.py", "backend/routes/teams.py", "backend/routes/players.py"],
            database_paths=["backend/models.py", "docs/DATABASE_SCHEMA.sql"],
            test_paths=["tests/test_analytics_api.py"],
            entrypoints=["frontend/src/main.jsx", "backend/main.py"],
            validation_profile={
                "check_imports": True,
                "check_frontend_routes": True,
                "check_backend_routes": True,
                "check_database_models": True,
                "check_auth_flow": profile.auth_required,
                "check_seed_data": True,
                "check_demo_materials": True,
            },
            architecture_overview=[
                "Sports analytics dashboard with team, player, and game-film views.",
                "Chart components backed by stats API routes.",
            ],
            rationale=rationale,
        )

    # Default adaptive web app — still not the old fixed StudyPilot shell.
    return ArchitecturePlan(
        file_tree=[
            "README.md",
            "package.json",
            "src/main.jsx",
            "src/App.jsx",
            "src/pages/Home.jsx",
            "src/pages/Workspace.jsx",
            "src/lib/api.js",
            "backend/main.py",
            "backend/models.py",
            "backend/routes/api.py",
            "backend/db.py",
            "data/seed.json",
            "tests/test_api.py",
            "docs/ARCHITECTURE.md",
            "docs/API_SPEC.md",
            "docs/DATABASE_SCHEMA.sql",
            "docs/DEPLOY.md",
            "docs/PROJECT_PLAN.md",
            "docs/TESTING_STRATEGY.md",
            "demo/script.md",
            "demo/storyboard.md",
            "demo/demo_walkthrough.md",
            "demo/video_outline.md",
        ],
        implementation_stages=["database", "backend", "frontend", "tests", "docs", "demo"],
        frontend_paths=["src/App.jsx", "src/pages/Home.jsx", "src/pages/Workspace.jsx"],
        backend_paths=["backend/main.py", "backend/routes/api.py"],
        database_paths=["backend/models.py", "docs/DATABASE_SCHEMA.sql"] if profile.database_required else [],
        test_paths=["tests/test_api.py"],
        entrypoints=["src/main.jsx", "backend/main.py"],
        validation_profile={
            "check_imports": True,
            "check_frontend_routes": profile.frontend_required,
            "check_backend_routes": profile.backend_required,
            "check_database_models": profile.database_required,
            "check_auth_flow": profile.auth_required,
            "check_seed_data": profile.database_required,
            "check_demo_materials": True,
        },
        architecture_overview=[
            f"Adaptive web application for category={category}.",
            "Stack and routes follow classified requirements rather than a fixed hackathon template.",
        ],
        rationale=rationale,
    )


class ArchitecturePlanner:
    """Plan repository structure from project profile and requirements."""

    def plan(
        self,
        profile: ProjectProfile,
        *,
        idea: str = "",
        recommended_stack: dict[str, Any] | None = None,
        requirements: dict[str, Any] | None = None,
        existing_plan: dict[str, Any] | None = None,
    ) -> ArchitecturePlan:
        del idea, recommended_stack, requirements  # reserved for future LLM merge
        blueprint = _blueprint_paths(profile)
        if not existing_plan:
            return blueprint

        existing_tree = [
            str(p).strip()
            for p in (existing_plan.get("file_tree") or existing_plan.get("files") or [])
            if str(p).strip()
        ]
        if not existing_tree or _looks_like_generic_web_tree(existing_tree):
            return blueprint

        merged_tree = sorted(set(existing_tree) | set(blueprint.file_tree) | UNIVERSAL_PATHS)
        blueprint.file_tree = merged_tree
        blueprint.rationale.append("Merged LLM plan with profile blueprint")
        return blueprint


def _looks_like_generic_web_tree(paths: list[str]) -> bool:
    """Detect the legacy GemPilot template tree."""
    legacy_markers = {
        "src/state/projectState.js",
        "src/lib/api.js",
        "backend/services.py",
        "scripts/seed_data.py",
    }
    hits = sum(1 for marker in legacy_markers if marker in paths)
    return hits >= 3


def plan_architecture(
    profile: ProjectProfile,
    *,
    idea: str = "",
    recommended_stack: dict[str, Any] | None = None,
    requirements: dict[str, Any] | None = None,
    existing_plan: dict[str, Any] | None = None,
) -> ArchitecturePlan:
    return ArchitecturePlanner().plan(
        profile,
        idea=idea,
        recommended_stack=recommended_stack,
        requirements=requirements,
        existing_plan=existing_plan,
    )


def architecture_plan_to_repo_plan(plan: ArchitecturePlan) -> dict[str, Any]:
    """Convert ArchitecturePlan into repo_plan-compatible dict for workflow state."""
    return {
        "files": plan.file_tree,
        "file_tree": plan.file_tree,
        "architecture_overview": plan.architecture_overview,
        "implementation_steps": [
            f"Implement stage: {stage}" for stage in plan.implementation_stages
        ],
        "frontend_architecture": plan.frontend_paths,
        "backend_architecture": plan.backend_paths,
        "data_model": plan.database_paths,
        "test_plan": plan.test_paths,
        "validation_profile": plan.validation_profile,
        "project_profile_rationale": plan.rationale,
    }


def get_gap_fill_paths(
    architecture_plan: dict[str, Any] | None,
    *,
    target_platform: str | None = None,
    is_hackathon_mode: bool = False,
) -> frozenset[str]:
    """Paths safe to gap-fill from scaffold without overwriting architecture."""
    del architecture_plan, target_platform
    paths = set(GAP_FILL_PATHS)
    if is_hackathon_mode:
        paths.update(HACKATHON_PATHS)
    return frozenset(paths)
