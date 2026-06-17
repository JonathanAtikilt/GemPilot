from __future__ import annotations

import json
from typing import Any


def _json_block(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _compact_planning_context(build_context: dict[str, Any]) -> dict[str, Any]:
    """Trim large RAG payloads for architecture calls to reduce gateway timeouts."""
    compact_keys = (
        "frontendIntake",
        "sourceContext",
        "recommendedStack",
        "resolvedTechStack",
        "projectDepth",
        "targetPlatform",
        "runtimeOrchestrationEnabled",
        "scopeWarnings",
        "requiredDeliverables",
        "requiredTechStackPieces",
    )
    compact = {key: build_context[key] for key in compact_keys if key in build_context}
    evidence = build_context.get("evidence")
    if isinstance(evidence, list) and evidence:
        compact["evidence"] = evidence[:12]
    return compact


def _context_contract() -> str:
    return (
        "Frontend intake is the user's source of truth for project identity, idea, "
        "target platform, project depth, submitted URLs, uploaded files, GitHub repository "
        "context, and final labels. Use frontendIntake, sourceContext, recommendedStack, "
        "and retrieval evidence as binding build context. "
        "Do not assume the generated project must use GemPilot's internal host stack "
        "(Next.js/FastAPI/Supabase used to run GemPilot). Recommend a project-specific stack "
        "from the idea, scope, target platform, complexity, and retrieved hackathon rules. "
        "Required RAG rules override user preference. After stack recommendation, "
        "resolvedTechStack and recommendedStack are binding for architecture, tests, and files. "
        "defaultItems / hostPlatformDefaults in build context are orchestrator-only hints, "
        "not the generated product stack. Surface missing or unreadable sources as warnings."
    )


def build_stack_recommendation_prompt(
    *,
    idea: str,
    project_requirements: dict[str, Any],
    build_context: dict[str, Any],
) -> str:
    return (
        "You are the Stack Selector Agent. Recommend the most effective tech stack for the "
        "generated software project — not for GemPilot itself.\n"
        "Analyze the project idea, depth, target platform, required features, and all "
        "RAG-retrieved hackathon rules, sponsor requirements, judging criteria, allowed/banned "
        "tools, APIs, SDKs, and deployment constraints.\n"
        "Do not blindly copy GemPilot's host stack. Prefer sponsor-required or sponsor-rewarded "
        "technologies when they fit the product. Label any fallback option as an alternative, "
        "not a silent default.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Prompt contract:\n{_context_contract()}\n\n"
        f"Frontend intake:\n{_json_block(build_context.get('frontendIntake', {}))}\n\n"
        f"Source context:\n{_json_block(build_context.get('sourceContext', {}))}\n\n"
        f"Project requirements:\n{_json_block(project_requirements)}\n\n"
        f"RAG hints (required stack pieces — not yet the final stack):\n"
        f"{_json_block(build_context.get('resolvedTechStack', {}))}\n\n"
        f"Structured build context:\n{_json_block(build_context)}\n\n"
        "Return frontend, backend, database, authentication, aiModels (list), orchestration (list), "
        "ragRetrieval, vectorStorage, deployment, testing, reasonForChoices, "
        "hackathonRuleAlignment, rejectedAlternatives, ruleConflicts, mode, and decision_trace."
    )


def build_requirements_prompt(
    *,
    idea: str,
    build_context: dict[str, Any],
    memory_matches: list[dict[str, Any]],
    retrieved_docs: list[dict[str, Any]] | None = None,
) -> str:
    del retrieved_docs
    return (
        "Expand this idea into a complete hackathon-ready full-stack project brief.\n"
        "Do not scope it down to a shallow prototype or generic starter app.\n"
        "The output must describe a polished, demo-ready generated project with real product "
        "depth, multiple features, data flows, authentication when relevant, sample data, "
        "tests, deployment readiness, and hackathon submission criteria.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Prompt contract:\n{_context_contract()}\n\n"
        f"Frontend intake:\n{_json_block(build_context.get('frontendIntake', {}))}\n\n"
        f"Source context:\n{_json_block(build_context.get('sourceContext', {}))}\n\n"
        f"RAG stack hints (Stack Selector finalizes the project stack next):\n"
        f"{_json_block(build_context.get('resolvedTechStack', {}))}\n\n"
        f"Structured build context:\n{_json_block(build_context)}\n\n"
        f"Memory matches:\n{_json_block(memory_matches)}\n\n"
        "Return target_users, user_personas, core_features, advanced_features, "
        "success_criteria, project_depth, target_platform, project_archetype, "
        "primary_entity, auth_required, database_required, data_entities, user_flows "
        "(3 or more steps with step, screen, action, api), api_routes, mode, and decision_trace. "
        "Default to Advanced Project or higher unless the user explicitly asks for Starter Project."
    )


def build_architecture_plan_prompt(
    *,
    idea: str,
    project_requirements: dict[str, Any],
    build_context: dict[str, Any],
) -> str:
    return (
        "Design the full generated repository architecture for this project.\n"
        "Plan a complete codebase, not a minimal demo or low-level scaffold. Include frontend, "
        "backend, data, API, auth, seed/sample data, testing, docs, deployment readiness, "
        "demo video materials, hackathon submission summary, and GitHub export tasks.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Prompt contract:\n{_context_contract()}\n\n"
        f"Frontend intake:\n{_json_block(build_context.get('frontendIntake', {}))}\n\n"
        f"Source context:\n{_json_block(build_context.get('sourceContext', {}))}\n\n"
        f"Project requirements:\n{_json_block(project_requirements)}\n\n"
        f"Recommended stack (binding):\n{_json_block(build_context.get('recommendedStack', {}))}\n\n"
        f"Resolved tech stack:\n{_json_block(build_context.get('resolvedTechStack', {}))}\n\n"
        f"Planning context (trimmed):\n{_json_block(_compact_planning_context(build_context))}\n\n"
        "Return files, file_tree, selected_stack, architecture_overview, frontend_architecture, "
        "backend_architecture, data_model, api_design, auth_design, database_schema, "
        "state_management, integration_points, implementation_steps, agent_assignments, "
        "github_actions_needed, generated_artifacts, security_constraints, test_plan, "
        "deployment_plan, documentation_plan, demo_video_plan, hackathon_submission_plan, "
        "mode, and decision_trace. "
        "Do not include secrets or real .env values."
    )


def build_file_manifest_prompt(
    *,
    idea: str,
    project_requirements: dict[str, Any],
    architecture_plan: dict[str, Any],
    build_context: dict[str, Any],
) -> str:
    return (
        "Create the generated artifact manifest for a complete full-stack software project.\n"
        "The manifest must support the architecture plan, user flows, auth/data/API design, "
        "seed/sample data, tests, README, setup guide, env guide, deployment notes, demo video "
        "materials, hackathon submission summary, and final project report.\n"
        "Do not emit a generic todo app, starter dashboard, or shallow fallback template.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Prompt contract:\n{_context_contract()}\n\n"
        f"Frontend intake:\n{_json_block(build_context.get('frontendIntake', {}))}\n\n"
        f"Source context:\n{_json_block(build_context.get('sourceContext', {}))}\n\n"
        f"Project requirements:\n{_json_block(project_requirements)}\n\n"
        f"Architecture plan:\n{_json_block(architecture_plan)}\n\n"
        f"Recommended stack:\n{_json_block(build_context.get('recommendedStack', {}))}\n\n"
        f"Resolved tech stack:\n{_json_block(build_context.get('resolvedTechStack', {}))}\n\n"
        f"Structured build context:\n{_json_block(build_context)}\n\n"
        "Return artifact names, kinds, one-line summaries, mode, and decision_trace. "
        "You may include file content, but if content is omitted the backend hydrates complete "
        "production-style files locally. Required paths include README.md, package.json, index.html, "
        "src/App.jsx, src/main.jsx, src/lib/api.js, src/state/projectState.js, src/styles.css, "
        "backend/main.py, backend/models.py, backend/services.py, backend/db.py, requirements.txt, "
        "tests/test_backend.py, docs/PROJECT_PLAN.md, docs/ARCHITECTURE.md, docs/API_SPEC.md, "
        "docs/DATABASE_SCHEMA.sql, docs/TESTING_STRATEGY.md, docs/DEPLOY.md, docs/AGENT_LOG.md, "
        "docs/BUILD_LOG.md, docs/KNOWN_LIMITATIONS.md, docs/WALKTHROUGH.md, "
        "docs/HACKATHON_SUBMISSION.md, data/seed.json, scripts/seed_data.py, "
        "demo/script.md, demo/storyboard.md, demo/demo_walkthrough.md, demo/video_outline.md, "
        "demo/voiceover.md, demo/demo_script.md, and .env.example."
    )


def build_blocker_analysis_prompt(
    *,
    idea: str,
    tool_result: dict[str, Any],
) -> str:
    return (
        "Analyze this blocked full-project generation result and decide whether it can recover.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Tool result:\n{_json_block(tool_result)}\n\n"
        "Return blocker type, severity, recoverable flag, root cause, recovery plan, and decision trace."
    )


def build_final_readme_prompt(
    *,
    idea: str,
    project_requirements: dict[str, Any],
    architecture_plan: dict[str, Any],
    generated_artifacts: list[dict[str, Any]],
    build_context: dict[str, Any],
) -> str:
    return (
        "Write the final README content for the generated full project.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Prompt contract:\n{_context_contract()}\n\n"
        f"Frontend intake:\n{_json_block(build_context.get('frontendIntake', {}))}\n\n"
        f"Source context:\n{_json_block(build_context.get('sourceContext', {}))}\n\n"
        f"Project requirements:\n{_json_block(project_requirements)}\n\n"
        f"Architecture plan:\n{_json_block(architecture_plan)}\n\n"
        f"Generated artifacts:\n{_json_block(generated_artifacts)}\n\n"
        "Return title, README markdown content, setup steps, and decision trace. "
        "Include product description, personas, features, architecture, env vars, setup, tests, "
        "deployment, demo instructions, hackathon submission summary, limitations, and future improvements."
    )


def build_walkthrough_prompt(
    *,
    idea: str,
    blocker_analysis: dict[str, Any] | None,
    build_context: dict[str, Any],
) -> str:
    return (
        "Write a concise product walkthrough for the generated project.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Prompt contract:\n{_context_contract()}\n\n"
        f"Frontend intake:\n{_json_block(build_context.get('frontendIntake', {}))}\n\n"
        f"Source context:\n{_json_block(build_context.get('sourceContext', {}))}\n\n"
        f"Resolved tech stack:\n{_json_block(build_context.get('resolvedTechStack', {}))}\n\n"
        f"Blocker analysis:\n{_json_block(blocker_analysis or {})}\n\n"
        "Return title, walkthrough content, beats, and decision trace."
    )


def build_demo_video_generation_prompt(
    *,
    idea: str,
    product_brief: dict[str, Any],
    stack: dict[str, Any],
    architecture: dict[str, Any],
    generated_file_names: list[str] | None = None,
) -> str:
    features = product_brief.get("core_features") or product_brief.get("must_have") or []
    user_flows = product_brief.get("user_flows") or product_brief.get("demo_path") or []
    api_routes = product_brief.get("api_routes") or architecture.get("api_design") or []
    file_list = generated_file_names or []

    return (
        "You are the Demo Video Generator Agent for a full-stack hackathon project generator.\n"
        "Generate repository demo materials that are specific to this product and suitable for "
        "recording a polished hackathon submission video. Do not write generic app-tour copy.\n\n"
        f"{_code_quality_rules()}\n"
        f"Product idea:\n{idea}\n\n"
        f"Product brief:\n{_json_block(product_brief)}\n\n"
        f"Tech stack:\n{_json_block(stack)}\n\n"
        f"Architecture:\n{_json_block(architecture)}\n\n"
        f"Core features: {_json_block(features)}\n"
        f"User flows: {_json_block(user_flows)}\n"
        f"API routes: {_json_block(api_routes)}\n"
        f"Generated files in this repo: {_json_block(file_list[:60])}\n\n"
        "Generate these files with FULL CONTENT:\n"
        "- demo/script.md — spoken demo script with timestamps and project-specific user flow\n"
        "- demo/storyboard.md — shot-by-shot storyboard tied to real app screens and data\n"
        "- demo/demo_walkthrough.md — click-by-click walkthrough for running the demo locally\n"
        "- demo/video_outline.md — recording outline with opening hook, product proof, technical proof, and close\n"
        "- demo/voiceover.md — optional voiceover copy, included when useful\n\n"
        "Also include a README demo-section patch as `docs/README_DEMO_SECTION.md` so the final "
        "README can link to these materials. Mention the actual frontend screens, backend routes, "
        "database entities, sample data, and tests that appear in this generated repository.\n\n"
        "Return JSON: { \"stage\": \"demo_video\", \"files\": [{\"name\", \"kind\", \"summary\", \"content\"}], "
        "\"decision_trace\": [...], \"mode\": \"live\" }"
    )


def build_pitch_prompt(
    *,
    idea: str,
    final_readme: dict[str, Any],
    walkthrough: dict[str, Any],
    build_context: dict[str, Any],
) -> str:
    return (
        "Write the final project report pitch for this generated codebase.\n\n"
        f"Idea:\n{idea}\n\n"
        f"Prompt contract:\n{_context_contract()}\n\n"
        f"Frontend intake:\n{_json_block(build_context.get('frontendIntake', {}))}\n\n"
        f"Source context:\n{_json_block(build_context.get('sourceContext', {}))}\n\n"
        f"Resolved tech stack:\n{_json_block(build_context.get('resolvedTechStack', {}))}\n\n"
        f"README:\n{_json_block(final_readme)}\n\n"
        f"Walkthrough:\n{_json_block(walkthrough)}\n\n"
        "Return title, tagline, pitch content, proof points, and decision trace."
    )


def _code_quality_rules() -> str:
    return (
        "CODE QUALITY RULES — non-negotiable:\n"
        "1. Write complete, working, production-quality source code in every file.\n"
        "2. Zero placeholder comments (no TODO, FIXME, PLACEHOLDER, or similar).\n"
        "3. Zero stub implementations (no bare `pass`, no `raise NotImplementedError`).\n"
        "4. Use the exact entity names, route paths, and field names from the product spec.\n"
        "5. Every import statement must reference a real file in this same repository.\n"
        "6. Every environment variable must appear in .env.example.\n"
        "7. Every frontend API call must match a backend route.\n"
        "8. Every database model must have a corresponding SQL table definition.\n"
    )


def build_database_generation_prompt(
    *,
    idea: str,
    product_brief: dict[str, Any],
    stack: dict[str, Any],
    architecture: dict[str, Any],
) -> str:
    data_entities = product_brief.get("data_entities") or architecture.get("data_model") or []
    auth_required = product_brief.get("auth_required", True)
    db_tech = stack.get("database", "SQLite (dev) / PostgreSQL (prod)")

    return (
        "You are the Database Generator Agent for a full-stack hackathon project generator.\n"
        "Generate ALL database-layer files for this product. Write complete, runnable code.\n\n"
        f"{_code_quality_rules()}\n"
        f"Product idea:\n{idea}\n\n"
        f"Product brief:\n{_json_block(product_brief)}\n\n"
        f"Database technology: {db_tech}\n"
        f"Auth required: {auth_required}\n"
        f"Data entities: {_json_block(data_entities)}\n\n"
        f"Architecture data model:\n{_json_block(architecture.get('data_model', {}))}\n\n"
        f"Architecture database schema:\n{_json_block(architecture.get('database_schema', {}))}\n\n"
        "Generate these files with FULL CONTENT (not just names):\n"
        "- backend/db.py — database engine, session factory, Base, and connection helpers\n"
        "- backend/models.py — SQLAlchemy ORM models for EVERY data entity with all fields, relationships, and __repr__\n"
        "- docs/DATABASE_SCHEMA.sql — complete DDL (CREATE TABLE, indexes, foreign keys, constraints) for all tables\n"
        "- scripts/seed_data.py — seed script that populates realistic sample data for all entities\n"
        "- alembic/env.py — Alembic migration environment (if SQL DB used)\n\n"
        "Use SQLAlchemy 2.x with async support. Include proper column types, defaults, nullable settings.\n"
        "For auth: include users table with hashed_password, email, created_at, and is_active.\n\n"
        "Return JSON: { \"stage\": \"database\", \"files\": [{\"name\", \"kind\", \"summary\", \"content\"}], "
        "\"decision_trace\": [...], \"mode\": \"live\" }"
    )


def build_backend_generation_prompt(
    *,
    idea: str,
    product_brief: dict[str, Any],
    stack: dict[str, Any],
    architecture: dict[str, Any],
    db_file_names: list[str] | None = None,
) -> str:
    features = product_brief.get("core_features") or []
    api_routes = product_brief.get("api_routes") or architecture.get("api_design") or []
    auth_required = product_brief.get("auth_required", True)
    backend_tech = stack.get("backend", "FastAPI + Python")
    auth_tech = stack.get("authentication", "JWT")

    return (
        "You are the Backend Generator Agent for a full-stack hackathon project generator.\n"
        "Generate ALL backend source files for this product. Write complete, runnable code.\n\n"
        f"{_code_quality_rules()}\n"
        f"Product idea:\n{idea}\n\n"
        f"Product brief:\n{_json_block(product_brief)}\n\n"
        f"Backend technology: {backend_tech}\n"
        f"Auth: {auth_tech if auth_required else 'No auth required'}\n"
        f"Core features: {_json_block(features)}\n"
        f"API routes: {_json_block(api_routes)}\n\n"
        f"Architecture backend plan:\n{_json_block(architecture.get('backend_architecture', {}))}\n\n"
        f"Auth design:\n{_json_block(architecture.get('auth_design', {}))}\n\n"
        f"Database files already generated: {db_file_names or ['backend/db.py', 'backend/models.py']}\n\n"
        "Generate these files with FULL CONTENT:\n"
        "- backend/main.py — FastAPI app factory with CORS, auth middleware, and all routers registered\n"
        "- backend/auth.py — JWT creation, password hashing (bcrypt), token validation, get_current_user dep\n"
        "- backend/routers/<feature>.py — one router file per major feature with all CRUD endpoints\n"
        "- backend/schemas.py — Pydantic v2 request/response models for EVERY API endpoint\n"
        "- backend/services/<feature>.py — business logic separated from route handlers\n"
        "- backend/middleware.py — CORS, rate limiting, request logging middleware\n"
        "- backend/config.py — Settings class reading from environment variables\n"
        "- .env.example — ALL required env vars with safe placeholder values\n"
        "- requirements.txt — pinned production and dev dependencies\n"
        "- tests/test_api.py — pytest tests for every route (happy path + error cases)\n\n"
        "Each router file must implement: list, get by id, create, update, delete endpoints.\n"
        "Use dependency injection for DB sessions. Include proper HTTP status codes and error messages.\n\n"
        "Return JSON: { \"stage\": \"backend\", \"files\": [{\"name\", \"kind\", \"summary\", \"content\"}], "
        "\"decision_trace\": [...], \"mode\": \"live\" }"
    )


def build_frontend_generation_prompt(
    *,
    idea: str,
    product_brief: dict[str, Any],
    stack: dict[str, Any],
    architecture: dict[str, Any],
    backend_routes: list[str] | None = None,
    data_entities: list[str] | None = None,
) -> str:
    features = product_brief.get("core_features") or []
    user_flows = product_brief.get("user_flows") or architecture.get("user_flows") or []
    frontend_tech = stack.get("frontend", "React + Vite + Tailwind CSS")
    state_mgmt = stack.get("state_management", "React Context + hooks")
    entities = data_entities or product_brief.get("data_entities") or []
    routes = backend_routes or product_brief.get("api_routes") or []

    return (
        "You are the Frontend Generator Agent for a full-stack hackathon project generator.\n"
        "Generate ALL frontend source files for this product. Write complete, runnable code.\n\n"
        f"{_code_quality_rules()}\n"
        f"Product idea:\n{idea}\n\n"
        f"Product brief:\n{_json_block(product_brief)}\n\n"
        f"Frontend technology: {frontend_tech}\n"
        f"State management: {state_mgmt}\n"
        f"Core features: {_json_block(features)}\n"
        f"Data entities: {_json_block(entities)}\n"
        f"Backend API routes: {_json_block(routes)}\n"
        f"User flows: {_json_block(user_flows)}\n\n"
        f"Frontend architecture plan:\n{_json_block(architecture.get('frontend_architecture', {}))}\n\n"
        "Generate these files with FULL CONTENT:\n"
        "- index.html — HTML shell with root div, viewport meta, and correct script src\n"
        "- package.json — all dependencies (react, react-dom, react-router-dom, axios, tailwindcss, etc.) with scripts\n"
        "- vite.config.js — Vite config with proxy to backend on port 8000\n"
        "- tailwind.config.js — Tailwind config with content paths\n"
        "- src/main.jsx — React entry with BrowserRouter wrapper\n"
        "- src/App.jsx — Route definitions for EVERY page\n"
        "- src/styles/globals.css — Tailwind directives + custom CSS variables\n"
        "- src/lib/api.js — Axios instance with auth headers + typed functions for EVERY backend route\n"
        "- src/contexts/AuthContext.jsx — user auth state, login/logout/register functions\n"
        "- src/pages/LandingPage.jsx — polished landing page with hero, features, and CTA\n"
        "- src/pages/LoginPage.jsx — login form with validation and error display\n"
        "- src/pages/RegisterPage.jsx — registration form\n"
        "- src/pages/Dashboard.jsx — main dashboard showing key metrics and recent activity\n"
        f"- src/pages/<Feature>Page.jsx — one full page per core feature: {', '.join(features[:5])}\n"
        "- src/components/Layout.jsx — sidebar/nav layout wrapper\n"
        "- src/components/Navbar.jsx — top navigation with user menu and logout\n"
        "- src/hooks/use<Entity>.js — one custom hook per data entity for CRUD operations\n\n"
        "Each page must be fully functional with real data loading, error states, and loading spinners.\n"
        "Use Tailwind CSS classes. No inline styles. Components must be responsive.\n"
        "API calls must use the exact route paths from the backend.\n\n"
        "Return JSON: { \"stage\": \"frontend\", \"files\": [{\"name\", \"kind\", \"summary\", \"content\"}], "
        "\"decision_trace\": [...], \"mode\": \"live\" }"
    )


def build_docs_generation_prompt(
    *,
    idea: str,
    product_brief: dict[str, Any],
    stack: dict[str, Any],
    architecture: dict[str, Any],
    generated_file_names: list[str] | None = None,
) -> str:
    features = product_brief.get("core_features") or []
    api_routes = product_brief.get("api_routes") or architecture.get("api_design") or []
    file_list = generated_file_names or []

    return (
        "You are the Documentation Generator Agent for a full-stack hackathon project generator.\n"
        "Generate ALL documentation files for this product. Write complete, accurate docs.\n\n"
        f"{_code_quality_rules()}\n"
        f"Product idea:\n{idea}\n\n"
        f"Product brief:\n{_json_block(product_brief)}\n\n"
        f"Tech stack:\n{_json_block(stack)}\n\n"
        f"Architecture:\n{_json_block(architecture)}\n\n"
        f"Core features: {_json_block(features)}\n"
        f"API routes: {_json_block(api_routes)}\n"
        f"Generated files in this repo: {_json_block(file_list[:40])}\n\n"
        "Generate these files with FULL CONTENT:\n"
        "- README.md — hero title, product description, feature list, quickstart (clone→install→env→run), "
        "architecture overview, env vars table, API summary, deployment instructions, tech stack badges\n"
        "- docs/ARCHITECTURE.md — system diagram (ASCII), component descriptions, data flow, "
        "service boundaries, infrastructure, scaling approach\n"
        "- docs/API_SPEC.md — full API reference: every route with method, path, auth requirement, "
        "request body schema, response schema, and curl example\n"
        "- docs/DATABASE_SCHEMA.md — entity-relationship description, table definitions, indexes, "
        "and data access patterns\n"
        "- docs/DEPLOY.md — step-by-step deployment for Vercel (frontend) + Railway/Render (backend) + "
        "Supabase/Neon (database), with environment variable checklist\n"
        "- docs/WALKTHROUGH.md — end-to-end product demo script: user opens app → signs up → "
        "uses each core feature → sees results, tied to generated demo files\n"
        "- docs/HACKATHON_SUBMISSION.md — concise submission summary with problem, solution, tech, "
        "differentiators, demo flow, and judging proof\n"
        "- docs/DEVELOPMENT.md — local dev setup, hot reload, running tests, linting, PR workflow\n\n"
        "README.md must be polished enough to be the GitHub repo's public face.\n"
        "README.md must include a Demo section that links to demo/script.md, demo/storyboard.md, "
        "demo/demo_walkthrough.md, and demo/video_outline.md. API_SPEC.md must document every "
        "endpoint that appears in the backend routers.\n\n"
        "Return JSON: { \"stage\": \"docs\", \"files\": [{\"name\", \"kind\", \"summary\", \"content\"}], "
        "\"decision_trace\": [...], \"mode\": \"live\" }"
    )


# Compatibility aliases for older imports.
build_scope_mvp_prompt = build_requirements_prompt
build_plan_repo_prompt = build_architecture_plan_prompt
build_demo_script_prompt = build_walkthrough_prompt
build_recommend_stack_prompt = build_stack_recommendation_prompt
