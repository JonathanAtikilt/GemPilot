from __future__ import annotations

import re
from typing import Any, Literal


ProjectDepth = Literal[
    "Starter Project",
    "Advanced Project",
    "Production-Style Project",
    "Hackathon-Winning Project",
]

DEFAULT_PROJECT_DEPTH: ProjectDepth = "Advanced Project"
PROJECT_DEPTHS: tuple[ProjectDepth, ...] = (
    "Starter Project",
    "Advanced Project",
    "Production-Style Project",
    "Hackathon-Winning Project",
)

TARGET_PLATFORMS = (
    "web app",
    "mobile app",
    "api",
    "ai agent",
    "browser extension",
    "dashboard",
    "desktop app",
)

PROJECT_ARCHETYPES: tuple[str, ...] = (
    "planner",
    "marketplace",
    "dashboard",
    "workflow",
    "content",
    "ai_system",
    "cli_tool",          # NEW: terminal tools, developer utilities
    "browser_extension", # NEW: browser extensions, content scripts
    "game",              # NEW: multiplayer or single-player games
    "data_pipeline",     # NEW: ETL, analytics, ML pipelines
    "library",           # NEW: SDKs, packages, developer libraries
)

ARCHETYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "planner": (
        "study",
        "schedule",
        "course",
        "planner",
        "calendar",
        "homework",
        "exam",
        "student",
        "learning",
        "spaced",
        "flashcard",
        "quiz",
    ),
    "marketplace": (
        "marketplace",
        "listing",
        "buy",
        "sell",
        "shop",
        "vendor",
        "rent",
        "booking",
    ),
    "dashboard": (
        "dashboard",
        "admin",
        "ops",
        "metrics",
        "monitor",
        "team",
        "queue",
        "ticket",
    ),
    "workflow": (
        "onboard",
        "application",
        "intake",
        "form",
        "approval",
        "submit",
        "workflow",
    ),
    "content": (
        "feed",
        "post",
        "publish",
        "blog",
        "content",
        "media",
        "share",
    ),
    "ai_system": (
        "ai",
        "agent",
        "copilot",
        "rag",
        "model",
        "summarize",
        "generate",
        "assistant",
    ),
    "cli_tool": (
        "cli",
        "terminal",
        "command line",
        "command-line",
        "developer tool",
        "git",
        "bash",
        "shell script",
        "npm package",
        "pip package",
        "devtools",
    ),
    "browser_extension": (
        "extension",
        "browser extension",
        "chrome extension",
        "firefox",
        "content script",
        "popup",
        "devtools panel",
        "web scraper extension",
    ),
    "game": (
        "game",
        "multiplayer",
        "chess",
        "puzzle",
        "quiz game",
        "trivia",
        "rpg",
        "shooter",
        "platformer",
        "board game",
        "card game",
    ),
    "data_pipeline": (
        "etl",
        "pipeline",
        "data pipeline",
        "data engineering",
        "analytics pipeline",
        "airflow",
        "spark",
        "kafka",
        "streaming",
        "batch processing",
    ),
    "library": (
        "sdk",
        "library",
        "npm package",
        "python package",
        "api client",
        "developer library",
        "open source library",
    ),
}

ARCHETYPE_API_ROUTES: dict[str, list[str]] = {
    "planner": [
        "POST /api/auth/login",
        "POST /api/uploads",
        "POST /api/files/upload",
        "GET /api/study-plan",
        "POST /api/study-plan",
        "POST /api/summaries",
        "POST /api/quizzes",
        "GET /api/flashcards/review",
        "GET /api/progress",
        "GET /api/dashboard",
    ],
    "marketplace": [
        "POST /api/auth/login",
        "GET /api/listings",
        "POST /api/listings",
        "POST /api/saved",
        "GET /api/dashboard",
    ],
    "dashboard": [
        "POST /api/auth/login",
        "GET /api/metrics",
        "GET /api/records",
        "PATCH /api/records/{id}",
        "GET /api/dashboard",
    ],
    "workflow": [
        "POST /api/auth/login",
        "POST /api/workflows",
        "GET /api/workflows",
        "PATCH /api/workflows/{id}",
        "GET /api/dashboard",
    ],
    "content": [
        "POST /api/auth/login",
        "GET /api/posts",
        "POST /api/posts",
        "GET /api/feed",
        "GET /api/dashboard",
    ],
    "ai_system": [
        "POST /api/auth/login",
        "POST /api/runs",
        "GET /api/runs/{id}",
        "POST /api/retrieval/query",
        "GET /api/dashboard",
    ],
    "cli_tool": [],  # CLI tools have no HTTP routes
    "browser_extension": [],  # Extensions have no HTTP routes
    "game": [
        "GET /api/leaderboard",
        "POST /api/games",
        "GET /api/games/{id}",
        "POST /api/games/{id}/move",
        "GET /api/players/{id}",
    ],
    "data_pipeline": [
        "POST /api/jobs",
        "GET /api/jobs/{id}/status",
        "GET /api/jobs/{id}/results",
        "GET /api/datasets",
    ],
    "library": [],  # Libraries have no HTTP routes
}


def normalize_project_depth(value: str | None) -> ProjectDepth:
    if not value:
        return DEFAULT_PROJECT_DEPTH
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    for depth in PROJECT_DEPTHS:
        if normalized == re.sub(r"[^a-z0-9]+", " ", depth.lower()).strip():
            return depth
    aliases = {
        "starter": "Starter Project",
        "advanced": "Advanced Project",
        "production": "Production-Style Project",
        "production style": "Production-Style Project",
        "hackathon": "Hackathon-Winning Project",
        "hackathon winning": "Hackathon-Winning Project",
    }
    return aliases.get(normalized, DEFAULT_PROJECT_DEPTH)  # type: ignore[return-value]


def depth_profile(depth: str | None) -> dict[str, Any]:
    normalized = normalize_project_depth(depth)
    profiles: dict[str, dict[str, Any]] = {
        "Starter Project": {
            "minimum_features": 4,
            "testing_layers": ["unit", "api smoke"],
            "documentation_depth": "setup plus architecture notes",
        },
        "Advanced Project": {
            "minimum_features": 7,
            "testing_layers": ["unit", "api integration", "frontend smoke"],
            "documentation_depth": "README, architecture, API, data model, deployment",
        },
        "Production-Style Project": {
            "minimum_features": 10,
            "testing_layers": ["unit", "api integration", "validation", "build"],
            "documentation_depth": "production setup, env, architecture, deployment, limitations",
        },
        "Hackathon-Winning Project": {
            "minimum_features": 12,
            "testing_layers": ["unit", "api integration", "frontend journey", "build", "demo validation"],
            "documentation_depth": "polished README, architecture, walkthrough, novelty, deployment",
        },
    }
    return {"name": normalized, **profiles[normalized]}


def classify_project_archetype(*, idea: str, required_features: list[str] | None = None) -> str:
    corpus = " ".join([idea, *(required_features or [])]).lower()
    idea_lower = idea.lower()

    def _has(term: str) -> bool:
        if len(term) <= 4:
            return re.search(rf"\b{re.escape(term)}\b", idea_lower) is not None
        return term in idea_lower

    # CLI tool detection — check before general keyword scoring
    if any(
        _has(kw)
        for kw in (
            "cli",
            "terminal",
            "command line",
            "command-line",
            "developer tool",
            "bash",
            "shell script",
            "devtools",
        )
    ) or "git" in idea_lower.split() or idea_lower.startswith("git "):
        return "cli_tool"

    # Browser extension detection
    if any(kw in idea_lower for kw in (
        "extension", "browser extension", "chrome extension", "firefox",
        "content script", "popup", "devtools panel", "web scraper extension",
    )):
        return "browser_extension"

    # Game detection
    if any(kw in idea_lower for kw in (
        "game", "multiplayer", "chess", "puzzle", "quiz game", "trivia",
        "rpg", "shooter", "platformer", "board game", "card game",
    )):
        return "game"

    # Data pipeline detection
    if any(kw in idea_lower for kw in (
        "etl", "pipeline", "data pipeline", "data engineering", "analytics pipeline",
        "airflow", "spark", "kafka", "streaming", "batch processing",
    )):
        return "data_pipeline"

    # Library / SDK detection
    if any(kw in idea_lower for kw in (
        "sdk", "library", "npm package", "python package", "api client",
        "developer library", "open source library",
    )):
        return "library"

    scores = {
        archetype: sum(1 for keyword in keywords if keyword in corpus)
        for archetype, keywords in ARCHETYPE_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return "workflow"


def primary_entity_for_archetype(archetype: str, idea: str) -> str:
    defaults = {
        "planner": "learning artifact",
        "marketplace": "listing",
        "dashboard": "work item",
        "workflow": "case",
        "content": "post",
        "ai_system": "agent run",
    }
    if "study" in idea.lower() or "lecture" in idea.lower():
        return "study asset"
    tokens = re.findall(r"[a-z]{4,}", idea.lower())
    for token in tokens:
        if token not in {"build", "create", "with", "that", "helps", "platform"}:
            return token.replace("_", " ")
    return defaults.get(archetype, "record")


def default_user_flows(
    *,
    archetype: str,
    idea: str,
    features: list[str],
    primary_entity: str,
) -> list[dict[str, str]]:
    feature_hint = features[0] if features else idea[:80]
    if archetype == "planner" and _looks_like_study_project(idea, features):
        return [
            {
                "step": "1",
                "screen": "Study Workspace",
                "action": "Sign in and upload lecture notes for parsing",
                "api": "POST /api/files/upload",
            },
            {
                "step": "2",
                "screen": "Study Planner",
                "action": "Generate a weekly plan from deadlines, weak topics, and uploaded notes",
                "api": "POST /api/study-plan",
            },
            {
                "step": "3",
                "screen": "AI Review Studio",
                "action": "Generate summaries, quizzes, and flashcards from the notes",
                "api": "POST /api/quizzes",
            },
            {
                "step": "4",
                "screen": "Exam Prep Dashboard",
                "action": "Review spaced repetition tasks, progress tracking, and personalized exam readiness",
                "api": "GET /api/progress",
            },
        ]

    templates: dict[str, list[dict[str, str]]] = {
        "planner": [
            {"step": "1", "screen": "Plan", "action": f"Review plan for {feature_hint}", "api": "GET /api/dashboard"},
            {"step": "2", "screen": "Create", "action": f"Create a new {primary_entity}", "api": "POST /api/uploads"},
            {"step": "3", "screen": "Review", "action": "Confirm next focus and progress", "api": "GET /api/dashboard"},
        ],
        "marketplace": [
            {"step": "1", "screen": "Browse", "action": "Browse personalized listings", "api": "GET /api/listings"},
            {"step": "2", "screen": "Detail", "action": f"Open a {primary_entity} detail workflow", "api": "GET /api/listings"},
            {"step": "3", "screen": "Action", "action": "Save or request the listing", "api": "POST /api/saved"},
        ],
        "dashboard": [
            {"step": "1", "screen": "Dashboard", "action": "Review system metrics", "api": "GET /api/metrics"},
            {"step": "2", "screen": "Queue", "action": "Filter active work items", "api": "GET /api/records"},
            {"step": "3", "screen": "Update", "action": "Update item status", "api": "PATCH /api/records/{id}"},
        ],
        "workflow": [
            {"step": "1", "screen": "Start", "action": "Begin the guided workflow", "api": "POST /api/workflows"},
            {"step": "2", "screen": "Steps", "action": "Complete required fields and validations", "api": "GET /api/workflows"},
            {"step": "3", "screen": "Done", "action": "Submit and view confirmation", "api": "GET /api/dashboard"},
        ],
        "content": [
            {"step": "1", "screen": "Feed", "action": "Browse recent content", "api": "GET /api/feed"},
            {"step": "2", "screen": "Create", "action": f"Draft a new {primary_entity}", "api": "POST /api/posts"},
            {"step": "3", "screen": "View", "action": "Open published content and analytics", "api": "GET /api/dashboard"},
        ],
        "ai_system": [
            {"step": "1", "screen": "Run Console", "action": "Start a model-backed run", "api": "POST /api/runs"},
            {"step": "2", "screen": "Evidence", "action": "Inspect retrieval and model output", "api": "POST /api/retrieval/query"},
            {"step": "3", "screen": "Dashboard", "action": "Review run status and next actions", "api": "GET /api/dashboard"},
        ],
    }
    return [dict(step) for step in templates.get(archetype, templates["workflow"])]


def default_api_routes(archetype: str) -> list[str]:
    return list(ARCHETYPE_API_ROUTES.get(archetype, ARCHETYPE_API_ROUTES["workflow"]))


def enrich_project_requirements(
    requirements: dict[str, Any],
    *,
    idea: str,
    intake: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from agent.project_classifier import apply_profile_to_requirements, classify_project

    intake = intake or {}
    explicit_features = _string_list(
        requirements.get("core_features")
        or requirements.get("must_have")
        or intake.get("requiredFeatures")
        or intake.get("required_features")
        or []
    )
    depth = normalize_project_depth(
        str(requirements.get("project_depth") or intake.get("projectDepth") or intake.get("project_depth") or "")
    )
    profile = depth_profile(depth)
    archetype = str(requirements.get("project_archetype") or requirements.get("vertical_pack") or "").strip().lower()
    if archetype not in PROJECT_ARCHETYPES:
        archetype = classify_project_archetype(idea=idea, required_features=explicit_features)
    primary_entity = (
        str(requirements.get("primary_entity") or "").strip()
        or primary_entity_for_archetype(archetype, idea)
    )
    core_features = _complete_feature_set(
        idea=idea,
        provided=explicit_features,
        minimum=int(profile["minimum_features"]),
    )
    user_flows = requirements.get("user_flows") or requirements.get("demo_path")
    if not isinstance(user_flows, list) or not user_flows:
        user_flows = default_user_flows(
            archetype=archetype,
            idea=idea,
            features=core_features,
            primary_entity=primary_entity,
        )
    api_routes = requirements.get("api_routes")
    if not isinstance(api_routes, list) or not api_routes:
        api_routes = default_api_routes(archetype)

    api_routes = requirements.get("api_routes")
    if not isinstance(api_routes, list) or not api_routes:
        api_routes = default_api_routes(archetype)

    advanced_features = _string_list(requirements.get("advanced_features") or [])
    target_platform = (
        str(requirements.get("target_platform") or intake.get("targetPlatform") or intake.get("target_platform") or "")
        .strip()
        .lower()
        or "web app"
    )

    project_profile = classify_project(idea, intake=intake, requirements=requirements)
    if requirements.get("auth_required") is None:
        auth_required = project_profile.auth_required
    else:
        auth_required = bool(requirements.get("auth_required"))
    if requirements.get("database_required") is None:
        database_required = project_profile.database_required
    else:
        database_required = bool(requirements.get("database_required"))

    merged = {
        **requirements,
        "project_depth": depth,
        "project_depth_profile": profile,
        "target_platform": target_platform,
        "project_archetype": archetype,
        "primary_entity": primary_entity,
        "target_users": requirements.get("target_users")
        or requirements.get("target_user")
        or intake.get("targetUsers")
        or intake.get("target_users")
        or "Users described in the submitted project idea",
        "user_personas": _string_list(requirements.get("user_personas") or [])
        or ["Primary user", "Admin or operator"],
        "core_features": core_features,
        "advanced_features": advanced_features,
        "success_criteria": _string_list(requirements.get("success_criteria") or [])
        or [
            "User can complete the primary end-to-end workflow",
            "Architecture, setup, testing, and deployment notes are generated",
        ],
        "auth_required": auth_required,
        "database_required": database_required,
        "data_entities": _string_list(requirements.get("data_entities") or [])
        or (["users", primary_entity.replace(" ", "_") + "s", "activity_logs"] if database_required else []),
        "api_routes": [str(route) for route in api_routes],
        "user_flows": user_flows,
        # Compatibility aliases for legacy workflow/UI keys.
        "vertical_pack": archetype,
        "must_have": core_features,
        "demo_path": user_flows,
        "project_boundary": str(
            requirements.get("project_boundary")
            or requirements.get("demo_boundary")
            or profile.get("summary", "One complete end-to-end workflow")
        ),
        "demo_boundary": str(
            requirements.get("demo_boundary")
            or requirements.get("project_boundary")
            or profile.get("summary", "One complete end-to-end workflow")
        ),
    }
    return apply_profile_to_requirements(merged, project_profile)


def project_tabs(archetype: str, idea: str = "") -> list[str]:
    if archetype == "planner" and "study" in idea.lower():
        return ["Workspace", "Generate", "Review", "Dashboard"]
    return {
        "planner": ["Plan", "Create", "Review", "Dashboard"],
        "marketplace": ["Browse", "Detail", "Saved", "Dashboard"],
        "dashboard": ["Dashboard", "Queue", "Insights", "Settings"],
        "workflow": ["Start", "Steps", "Review", "Dashboard"],
        "content": ["Feed", "Create", "Library", "Dashboard"],
        "ai_system": ["Console", "Evidence", "Runs", "Dashboard"],
    }.get(archetype, ["Workspace", "Build", "Review", "Dashboard"])


def project_collection_route(archetype: str) -> str:
    return {
        "planner": "/api/uploads",
        "marketplace": "/api/listings",
        "dashboard": "/api/records",
        "workflow": "/api/workflows",
        "content": "/api/posts",
        "ai_system": "/api/runs",
    }.get(archetype, "/api/workflows")


def deploy_readme_section(*, project_title: str, repo_url: str | None) -> str:
    repo_line = repo_url or "<your-github-repo-url>"
    return (
        f"# Deploy {project_title}\n\n"
        "## Frontend\n\n"
        "1. Import the GitHub repository in Vercel, Netlify, or another static host.\n"
        "2. Build command: `npm run build`.\n"
        "3. Output directory: `dist`.\n"
        "4. Set `VITE_API_BASE_URL` to the deployed backend URL.\n\n"
        "## Backend\n\n"
        "1. Deploy `backend/` as a Python web service on Render, Railway, Fly.io, or a container host.\n"
        "2. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.\n"
        "3. Set `DATABASE_URL`, auth secrets, and provider keys in the backend environment.\n"
        "4. Run the SQL in `docs/DATABASE_SCHEMA.sql` on your Postgres/Supabase project.\n\n"
        f"Repository: {repo_line}\n"
    )


def build_deploy_artifact(*, project_title: str, repo_url: str | None) -> dict[str, str]:
    return {
        "name": "docs/DEPLOY.md",
        "kind": "markdown",
        "summary": "Deployment instructions for frontend, backend, database, and environment variables.",
        "content": deploy_readme_section(project_title=project_title, repo_url=repo_url),
    }


def user_flow_checklist(user_flows: list[dict[str, Any]]) -> list[str]:
    checklist: list[str] = []
    for step in user_flows:
        if not isinstance(step, dict):
            continue
        label = str(step.get("action") or step.get("screen") or step.get("step") or "Step")
        api = str(step.get("api") or "").strip()
        checklist.append(f"{label} ({api})" if api else label)
    return checklist


def _complete_feature_set(*, idea: str, provided: list[str], minimum: int) -> list[str]:
    """Keep explicit features plus only logically implied ones — no template stuffing."""
    features = _unique_strings(provided)
    if features:
        return features

    # Derive minimal features from the idea itself when none were supplied.
    sentences = [part.strip(" .") for part in re.split(r"[.;\n]", idea) if part.strip()]
    for sentence in sentences:
        if len(features) >= max(minimum, 1):
            break
        if len(sentence) >= 8 and sentence not in features:
            features.append(sentence[:120])
    return features[: max(minimum, len(provided), 3)]


def _looks_like_study_project(idea: str, features: list[str]) -> bool:
    corpus = " ".join([idea, *features]).lower()
    return any(word in corpus for word in ("study", "lecture", "quiz", "flashcard", "spaced repetition", "exam"))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = re.sub(r"\s+", " ", str(value)).strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def title_from_idea(idea: str) -> str:
    label = re.sub(r"\s+", " ", idea.rstrip(".")).strip()
    lowered = label.lower()
    for prefix in ("build a ", "build an ", "create a ", "make a "):
        if lowered.startswith(prefix):
            label = label[len(prefix) :]
            break
    if len(label) > 72:
        label = f"{label[:69].rstrip()}..."
    return label[:1].upper() + label[1:] if label else "Generated Project"
