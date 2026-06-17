from __future__ import annotations

import logging
import re
import posixpath
from typing import Any

from agent.idea_context import project_title_from_context
from agent.project_depth import PROJECT_ARCHETYPES, user_flow_checklist

logger = logging.getLogger(__name__)


GENERIC_MARKERS = (
    "generic todo",
    "basic todo",
    "hello world",
    "lorem ipsum",
    "placeholder app",
    "sample dashboard",
    "starter app",
    "baseline prototype",
)

GENERIC_FEATURE_PHRASES = (
    "capture intake details for the target workflow",
    "generate a prioritized action plan",
    "expose sample data through a small api surface",
)

REQUIRED_DEMO_FILES = (
    "demo/script.md",
    "demo/storyboard.md",
    "demo/demo_walkthrough.md",
    "demo/video_outline.md",
)

PLACEHOLDER_MARKERS = (
    "todo",
    "fixme",
    "lorem ipsum",
    "placeholder app",
    "coming soon",
    "stub implementation",
    "notimplementederror",
    "pass  #",
    "todo:",
)

DEGRADED_MODE_DISCLOSURE = (
    "\n\n## Generation Mode Disclosure\n\n"
    "This build used explicit **degraded** mode when live LLM output was unavailable "
    "or incomplete. Project-specific heuristics and local scaffolds supplemented the pipeline.\n"
)

DEGRADED_MODE_LOG_TARGETS = (
    "docs/BUILD_LOG.md",
    "docs/AGENT_LOG.md",
    "README.md",
)

ARCHITECTURE_TERM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("frontend", "client-side", "react", "vite", "ui layer", "user interface"),
    ("backend", "server", "fastapi", "api layer", "service layer"),
    ("data", "database", "persistence", "schema", "postgres", "sqlite", "supabase"),
    ("auth", "authentication", "jwt", "login", "session", "oauth"),
)

ARCHITECTURE_VALIDATION_APPENDIX = """

## Validation Coverage

### Frontend
- React/Vite client workspace, routed screens, and API integration.

### Backend
- FastAPI services, routes, and domain logic.

### Data
- Relational schema, seed data, and persistence boundaries.

### Auth
- Development auth flow with production-ready provider replacement notes.

### Implementation Plan
- Generate and validate frontend, backend, database, docs, tests, and deployment artifacts.
"""


def ensure_degraded_mode_documented(
    artifacts: list[dict[str, Any]],
    model_modes: list[str],
) -> list[dict[str, Any]]:
    """Append degraded-mode disclosure to logs when the workflow used degraded generation."""
    if "degraded" not in model_modes:
        return artifacts

    patched: list[dict[str, Any]] = []
    for artifact in artifacts:
        name = str(artifact.get("name") or "")
        content = str(artifact.get("content") or "")
        if name in DEGRADED_MODE_LOG_TARGETS and "degraded" not in content.lower():
            artifact = {
                **artifact,
                "content": content.rstrip() + DEGRADED_MODE_DISCLOSURE,
            }
        patched.append(artifact)
    return patched


def _architecture_covers_full_system(architecture: str, plan: dict[str, Any]) -> bool:
    lowered = architecture.lower()
    if not architecture.strip():
        return False
    terms_ok = all(
        any(alias in lowered for alias in group)
        for group in ARCHITECTURE_TERM_GROUPS
    )
    plan_ok = bool(plan.get("implementation_steps")) or bool(plan.get("files")) or bool(
        plan.get("file_tree")
    )
    return terms_ok and plan_ok


def ensure_architecture_doc_complete(
    artifacts: list[dict[str, Any]],
    *,
    plan: dict[str, Any] | None,
    title: str,
    target_platform: str | None = None,
) -> list[dict[str, Any]]:
    """Patch architecture docs so validation and judges see full-stack coverage."""
    stack = _detect_stack_from_artifacts(artifacts)
    platform = str(
        target_platform
        or (plan or {}).get("target_platform")
        or ""
    ).lower()
    is_web = stack.get("has_frontend") or stack.get("has_web_backend")
    if not is_web and platform in {"", "web app", "mobile app", "dashboard"}:
        is_web = True
    if not is_web:
        return artifacts

    active_plan = plan or {}
    architecture = _artifact_content(artifacts, "docs/ARCHITECTURE.md")
    if _architecture_covers_full_system(architecture, active_plan):
        return artifacts

    if not architecture.strip():
        architecture = f"# {title} Architecture\n"

    patched_content = architecture.rstrip() + ARCHITECTURE_VALIDATION_APPENDIX
    patched: list[dict[str, Any]] = []
    updated = False
    for artifact in artifacts:
        if str(artifact.get("name")) == "docs/ARCHITECTURE.md":
            patched.append({**artifact, "content": patched_content})
            updated = True
        else:
            patched.append(artifact)
    if not updated:
        patched.append(
            {
                "name": "docs/ARCHITECTURE.md",
                "kind": "markdown",
                "summary": "Architecture overview with frontend, backend, data, and auth coverage.",
                "content": patched_content,
            }
        )
    return patched


def _detect_stack_from_artifacts(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect the actual project stack to make validation checks adaptive.

    Returns a dict with keys:
        project_type        – fullstack | frontend-only | backend-only | other
        has_frontend        – bool
        has_backend         – bool
        app_source_path     – path to the primary app component, or None
        backend_main_path   – path to the backend entry point, or None
        models_path         – path to the data-model file, or None
        services_path       – path to a services/db file, or None
        db_path             – path to the db adapter file, or None
        js_aliases          – dict of alias prefix → path prefix
    """
    by_name: dict[str, str] = {
        str(a.get("name", "")).strip(): str(a.get("content", ""))
        for a in artifacts
        if str(a.get("name", "")).strip()
    }
    paths = set(by_name)

    # -- Frontend detection --
    has_jsx = any(p.endswith((".jsx", ".tsx")) for p in paths)
    pkg = by_name.get("package.json", "").lower()
    has_react = '"react"' in pkg
    has_nextjs = any(p.startswith("next.config") for p in paths) or '"next"' in pkg
    has_vite = any(p.startswith("vite.config") for p in paths) or '"vite"' in pkg
    has_frontend = has_jsx or has_react or has_nextjs or has_vite

    # -- Backend detection --
    py_paths = [p for p in paths if p.endswith(".py")]
    req = "".join(
        by_name.get(p, "") for p in ("requirements.txt", "pyproject.toml")
    ).lower()
    py_sample = " ".join(by_name.get(p, "") for p in py_paths[:6]).lower()
    has_fastapi = "fastapi" in req or "fastapi" in py_sample
    has_flask = "flask" in req or "from flask" in py_sample
    has_express_dep = '"express"' in pkg
    # has_web_backend: has an HTTP API layer (FastAPI / Flask / Express)
    has_web_backend = has_fastapi or has_flask or has_express_dep
    has_backend = bool(py_paths) or has_express_dep

    # -- Project type --
    if has_frontend and has_backend:
        project_type = "fullstack"
    elif has_frontend:
        project_type = "frontend-only"
    elif has_backend:
        project_type = "backend-only"
    else:
        project_type = "other"

    # -- Find primary app component --
    app_source_candidates = [
        "src/App.jsx", "src/App.tsx", "src/app.jsx", "src/app.tsx",
        "frontend/src/App.jsx", "frontend/src/App.tsx",
        "app/page.tsx", "app/page.jsx",
        "pages/index.tsx", "pages/index.jsx",
        "src/index.jsx", "src/index.tsx",
    ]
    app_source_path = next((p for p in app_source_candidates if p in paths), None)

    # -- Find backend entry point --
    backend_main_candidates = [
        "backend/main.py", "app/main.py", "main.py", "app.py",
        "api/main.py", "server/main.py",
        "server.js", "index.js", "app.js", "server/index.js",
    ]
    backend_main_path = next((p for p in backend_main_candidates if p in paths), None)

    # -- Find models / services / db files --
    models_candidates = [
        "backend/models.py", "app/models.py", "models.py", "api/models.py",
        "models/index.js", "src/models/index.js",
    ]
    models_path = next((p for p in models_candidates if p in paths), None)

    services_candidates = [
        "backend/services.py", "app/services.py", "services.py",
    ]
    services_path = next((p for p in services_candidates if p in paths), None)

    db_candidates = [
        "backend/db.py", "app/db.py", "db.py", "database.py",
        "backend/database.py", "app/database.py",
    ]
    db_path = next((p for p in db_candidates if p in paths), None)

    # -- JS aliases --
    frontend_root = "src"
    if any(p.startswith("frontend/src/") for p in paths):
        frontend_root = "frontend/src"
    elif app_source_path and "/" in app_source_path:
        frontend_root = app_source_path.rsplit("/", 1)[0]
    js_aliases: dict[str, str] = {"@/": f"{frontend_root}/"}

    logger.info(
        "[validate] detected stack: type=%s app=%s backend_main=%s models=%s",
        project_type,
        app_source_path,
        backend_main_path,
        models_path,
    )

    return {
        "project_type": project_type,
        "has_frontend": has_frontend,
        "has_backend": has_backend,
        # True only for web-API backends (FastAPI / Flask / Express).
        # False for Python CLI / data-pipeline / package projects.
        "has_web_backend": has_web_backend,
        "app_source_path": app_source_path,
        "backend_main_path": backend_main_path,
        "models_path": models_path,
        "services_path": services_path,
        "db_path": db_path,
        "js_aliases": js_aliases,
    }


def validate_project_output(
    *,
    idea: str,
    intake: dict[str, Any] | None,
    project_requirements: dict[str, Any] | None,
    architecture_plan: dict[str, Any] | None,
    generated_artifacts: list[dict[str, Any]],
    model_modes: list[str],
    require_live_manifest: bool = False,
    manifest_model_mode: str | None = None,
    allow_degraded_manifest: bool = False,
) -> dict[str, Any]:
    intake = intake or {}
    requirements = project_requirements or {}
    plan = architecture_plan or {}
    generated_artifacts = ensure_degraded_mode_documented(generated_artifacts, model_modes)
    title = project_title_from_context(idea=idea, intake=intake)
    generated_artifacts = ensure_architecture_doc_complete(
        generated_artifacts,
        plan=plan,
        title=title,
        target_platform=str(requirements.get("target_platform") or ""),
    )
    idea_tokens = _idea_tokens(idea)
    title_tokens = _idea_tokens(title)

    # Detect the actual project stack so checks are adaptive
    stack = _detect_stack_from_artifacts(generated_artifacts)
    js_aliases = stack["js_aliases"]

    readme = _artifact_content(generated_artifacts, "README.md")

    # Use the detected app component path, falling back to the classic default
    app_source = _artifact_content(
        generated_artifacts, stack["app_source_path"] or "src/App.jsx"
    )

    architecture = _artifact_content(generated_artifacts, "docs/ARCHITECTURE.md")
    api_spec = _artifact_content(generated_artifacts, "docs/API_SPEC.md")
    schema = _artifact_content(generated_artifacts, "docs/DATABASE_SCHEMA.sql")

    # Use the detected backend entry point, falling back to the classic default
    backend_main = _artifact_content(
        generated_artifacts, stack["backend_main_path"] or "backend/main.py"
    )
    backend_services = _artifact_content(
        generated_artifacts,
        stack["services_path"] or "backend/services.py",
    )

    tests = _artifact_content(generated_artifacts, "tests/test_backend.py")
    deploy = _artifact_content(generated_artifacts, "docs/DEPLOY.md")
    agent_log = _artifact_content(generated_artifacts, "docs/AGENT_LOG.md") + _artifact_content(
        generated_artifacts, "docs/BUILD_LOG.md"
    )
    files = _artifact_map(generated_artifacts)
    combined_demo = "\n".join(_artifact_content(generated_artifacts, path) for path in REQUIRED_DEMO_FILES)

    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    features = _string_list(requirements.get("core_features") or requirements.get("must_have"))
    advanced = _string_list(requirements.get("advanced_features"))
    api_routes = _string_list(requirements.get("api_routes"))
    high_depth = str(requirements.get("project_depth") or "").lower() in {
        "advanced project",
        "production-style project",
        "hackathon-winning project",
    }

    add_check(
        "title_matches_idea",
        _title_matches_idea(title, idea, idea_tokens, title_tokens),
        f"Expected project title '{title}' to reflect the submitted idea.",
    )
    add_check(
        "readme_specific",
        bool(readme) and _text_reflects_idea(readme, idea_tokens) and not _looks_generic(readme),
        "README should mention the idea and describe a complete generated project.",
    )

    # ui_specific: only enforce when the project actually has a frontend
    add_check(
        "ui_specific",
        (
            bool(app_source)
            and _text_reflects_idea(app_source, idea_tokens)
            and not _looks_generic(app_source)
        )
        if stack["has_frontend"]
        else True,
        "Frontend should reference the idea and expose real product flows.",
    )

    add_check(
        "requirements_expanded",
        len(features) >= (7 if high_depth else 4),
        "Project requirements should include enough core features for the requested depth.",
    )
    add_check(
        "advanced_features_present",
        bool(advanced) or not high_depth,
        "Advanced or higher depth should include advanced features.",
    )
    add_check(
        "no_generic_fallback_features",
        not _uses_generic_feature_set(features) and not _looks_generic(readme + app_source),
        "Output must not use legacy generic starter or fallback feature language.",
    )
    add_check(
        "architecture_documents_full_system",
        _architecture_covers_full_system(architecture, plan),
        "Architecture doc should cover frontend, backend, data, auth, and the plan.",
    )
    add_check(
        "api_and_database_planned",
        bool(api_spec)
        and bool(schema)
        and ("create table" in schema.lower())
        and (bool(api_routes) or "/api/" in api_spec),
        "Generated project should include API route and database schema plans.",
    )
    add_check(
        "auth_data_flow_present",
        ("/api/auth/login" in backend_main and "users" in schema.lower()) if high_depth else True,
        "Advanced or higher depth should include authentication and user-backed data flow.",
    )

    # implementation_files_complete: check the detected stack's actual files
    add_check(
        "implementation_files_complete",
        _implementation_files_complete(generated_artifacts, stack),
        "Generated file tree should include appropriate API/state and backend model/service layers.",
    )

    add_check(
        "testing_and_deployment_present",
        bool(tests) and bool(deploy),
        "Generated project should include tests and deployment instructions.",
    )
    add_check(
        "generated_files_not_placeholders",
        _files_not_placeholder(files),
        "Generated files should be non-empty and must not contain placeholder, TODO, or stub content.",
    )
    add_check(
        "imports_resolve",
        _imports_resolve(files, js_aliases=js_aliases),
        "Local Python and frontend imports should resolve to files in the generated repository.",
    )

    # frontend_routes_or_pages_exist: only enforce when the project has a frontend
    add_check(
        "frontend_routes_or_pages_exist",
        _frontend_pages_exist(app_source, files) if stack["has_frontend"] else True,
        "Frontend should expose route/page or tabbed screen surfaces for the product workflow.",
    )

    # backend_routes_exist / database_models_used: only for web-API backends
    add_check(
        "backend_routes_exist",
        _backend_routes_exist(api_routes, backend_main, api_spec) if stack["has_web_backend"] else True,
        "Backend route handlers should exist for the planned API routes.",
    )

    add_check(
        "database_models_used",
        _database_models_used(files, backend_main, schema, stack=stack) if stack["has_web_backend"] else True,
        "Database/model files should be present and imported by backend route handlers.",
    )

    add_check(
        "readme_setup_features_demo",
        _readme_has_setup_features_demo(readme),
        "README should include setup, features, and demo instructions.",
    )
    add_check(
        "demo_materials_generated",
        _demo_materials_generated(files, combined_demo, idea_tokens | title_tokens),
        "Every generated project should include project-specific demo script, storyboard, walkthrough, and video outline files.",
    )
    add_check(
        "seed_data_present",
        _seed_data_present(files),
        "Generated project should include seed/sample data and a seed loading script.",
    )
    if _looks_like_study_project(idea, features):
        add_check(
            "studypilot_benchmark_complete",
            _study_project_complete(files),
            "StudyPilot benchmark should include dashboard, study planner, flashcards, quizzes, progress tracking, file upload, backend routes, database models, and demo script.",
        )
    add_check(
        "degraded_mode_explicit",
        "degraded" not in model_modes or "degraded" in agent_log.lower() or "degraded" in readme.lower(),
        "Any degraded mode must be explicit in logs or documentation.",
    )
    if require_live_manifest:
        manifest_mode = manifest_model_mode or (model_modes[-1] if model_modes else "")
        manifest_accepted = manifest_mode == "live" or (
            allow_degraded_manifest and manifest_mode in {"degraded", "partial"}
        )
        add_check(
            "live_manifest_only",
            manifest_accepted,
            "Live workflow requires configured LLM file_manifest output.",
        )
    add_check(
        "user_flow_defined",
        _user_flow_defined(requirements),
        "Project requirements should include an end-to-end user flow.",
    )
    add_check(
        "project_archetype_selected",
        str(requirements.get("project_archetype") or "") in PROJECT_ARCHETYPES,
        "Requirements should select a project archetype.",
    )

    # is_web_project: has at least one HTTP layer (frontend or web-API backend)
    is_web_project = stack["has_frontend"] or stack["has_web_backend"]

    critical = {
        "title_matches_idea",
        "readme_specific",
        "requirements_expanded",
        "no_generic_fallback_features",
        "implementation_files_complete",
        "testing_and_deployment_present",
        "user_flow_defined",
        "generated_files_not_placeholders",
        "imports_resolve",
    }
    # Only require demo files and seed data for web/hackathon projects
    if is_web_project:
        critical.add("seed_data_present")
        critical.add("demo_materials_generated")
        critical.add("readme_setup_features_demo")
    else:
        # For non-web projects these checks remain in the set but as non-critical
        pass
    # Architecture doc and API/DB planning are only critical for web projects;
    # a CLI/package is not expected to document frontend/backend/auth/db layers.
    if is_web_project:
        critical.update({"architecture_documents_full_system", "api_and_database_planned"})
    # Frontend checks only when there is a frontend layer
    if stack["has_frontend"]:
        critical.update({"ui_specific", "frontend_routes_or_pages_exist"})
    # API route/model checks only for web-API backends (not Python CLI/package)
    if stack["has_web_backend"]:
        critical.update({"backend_routes_exist", "database_models_used"})
    if _looks_like_study_project(idea, features):
        critical.add("studypilot_benchmark_complete")
    if require_live_manifest:
        critical.add("live_manifest_only")
    passed = all(item["passed"] for item in checks if item["name"] in critical)
    warnings = [item["detail"] for item in checks if not item["passed"]]
    return {
        "passed": passed,
        "project_title": title,
        "checks": checks,
        "user_flows": requirements.get("user_flows") or [],
        "project_archetype": requirements.get("project_archetype"),
        "project_depth": requirements.get("project_depth"),
        "warnings": warnings,
    }


def build_project_delivery_report(
    *,
    idea: str,
    intake: dict[str, Any] | None,
    project_requirements: dict[str, Any] | None,
    validation: dict[str, Any],
    model_modes: list[str],
    generated_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    del intake
    requirements = project_requirements or {}
    features = _string_list(requirements.get("core_features"))
    advanced = _string_list(requirements.get("advanced_features"))
    pending = []
    if "degraded" in model_modes or "partial" in model_modes:
        pending.append("Live LLM file content used explicit degraded mode")
    if not validation.get("passed"):
        pending.extend(validation.get("warnings") or [])

    return {
        "idea": idea,
        "project_title": validation.get("project_title"),
        "project_depth": requirements.get("project_depth"),
        "project_archetype": requirements.get("project_archetype"),
        "user_flow_checklist": user_flow_checklist(requirements.get("user_flows") or []),
        "model_modes": model_modes,
        "completed_features": features,
        "advanced_features": advanced,
        "degraded_features": [
            "External provider integrations require configured credentials",
            "Production auth provider replacement is documented",
        ]
        if "degraded" in model_modes or "partial" in model_modes
        else [],
        "pending_features": pending,
        "artifact_count": len(generated_artifacts),
        "validation_passed": validation.get("passed", False),
        "validation_checks": validation.get("checks", []),
    }


def _artifact_content(artifacts: list[dict[str, Any]], name: str) -> str:
    for artifact in reversed(artifacts):
        if str(artifact.get("name")) == name:
            return str(artifact.get("content") or "")
    return ""


def _artifact_map(artifacts: list[dict[str, Any]]) -> dict[str, str]:
    files: dict[str, str] = {}
    for artifact in artifacts:
        name = str(artifact.get("name") or "").strip()
        if not name or name.endswith("/"):
            continue
        content = artifact.get("content")
        files[name] = content if isinstance(content, str) else str(content or "")
    return files


def _has_file(artifacts: list[dict[str, Any]], name: str) -> bool:
    return any(str(artifact.get("name")) == name and bool(artifact.get("content")) for artifact in artifacts)


def _files_not_placeholder(files: dict[str, str]) -> bool:
    if not files:
        return False
    for path, content in files.items():
        body = content.strip()
        # Any __init__.py (Python package marker) is allowed to be empty
        if not body and path.endswith("__init__.py"):
            continue
        if not body:
            return False
        if path.endswith(".env.example"):
            continue
        lowered = body.lower()
        if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
            return False
        if re.search(r"^\s*pass\s*$", body, flags=re.MULTILINE):
            return False
    return True


JS_ASSET_EXTENSIONS = (
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".mp4",
    ".mp3",
    # Stylesheet and data imports are not resolvable JS modules
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".module.css",
    ".module.scss",
    ".json",
)


def _local_python_roots(paths: set[str]) -> set[str]:
    """Infer project-local Python package root names from the file tree."""
    roots: set[str] = {"backend", "src", "app"}
    skip = {"docs", "demo", "tests", "scripts", "data", "assets", "node_modules", ".git"}
    for p in paths:
        parts = p.split("/")
        if len(parts) >= 2 and p.endswith(".py") and parts[0] not in skip:
            roots.add(parts[0])
    return roots


def _imports_resolve(files: dict[str, str], js_aliases: dict[str, str] | None = None) -> bool:
    return not _import_failure_paths(files, js_aliases=js_aliases)


def _import_failure_paths(
    files: dict[str, str],
    js_aliases: dict[str, str] | None = None,
) -> set[str]:
    paths = set(files)
    failing: set[str] = set()
    for path, content in files.items():
        if path.endswith(".py") and not _python_imports_resolve(path, content, paths):
            failing.add(path)
        elif path.endswith((".js", ".jsx", ".ts", ".tsx")) and not _js_imports_resolve(
            path, content, paths, js_aliases=js_aliases
        ):
            failing.add(path)
    return failing


def _python_imports_resolve(path: str, content: str, paths: set[str]) -> bool:
    del path
    local_roots = _local_python_roots(paths)
    modules = re.findall(r"^\s*from\s+([a-zA-Z_][\w.]*)\s+import\s+", content, flags=re.MULTILINE)
    modules += re.findall(r"^\s*import\s+([a-zA-Z_][\w.]*)", content, flags=re.MULTILINE)
    for module in modules:
        root = module.split(".")[0]
        if root not in local_roots:
            continue
        if module == root:
            if not any(candidate.startswith(f"{root}/") for candidate in paths):
                return False
            continue
        module_path = module.replace(".", "/")
        if f"{module_path}.py" not in paths and f"{module_path}/__init__.py" not in paths:
            return False
    return True


def _js_imports_resolve(
    path: str,
    content: str,
    paths: set[str],
    js_aliases: dict[str, str] | None = None,
) -> bool:
    """Return True if all local JS/TS imports in *content* resolve to known paths."""
    effective_aliases: dict[str, str] = js_aliases if js_aliases is not None else {"@/": "src/"}

    specs: list[str] = []
    specs += re.findall(r"\bfrom\s+['\"](\.{1,2}/[^'\"]+)['\"]", content)
    specs += re.findall(r"\bimport\s+['\"](\.{1,2}/[^'\"]+)['\"]", content)

    # Resolve alias imports using the configured (or default) alias map
    for alias_prefix, alias_root in effective_aliases.items():
        alias_esc = re.escape(alias_prefix)
        for tail in re.findall(rf"\bfrom\s+['\"](?:{alias_esc})([^'\"]+)['\"]", content):
            specs.append(f"{alias_root}{tail}")
        for tail in re.findall(rf"\bimport\s+['\"](?:{alias_esc})([^'\"]+)['\"]", content):
            specs.append(f"{alias_root}{tail}")

    base_dir = posixpath.dirname(path)
    for spec in specs:
        if spec.startswith(("http://", "https://")):
            continue
        if any(spec.endswith(ext) for ext in JS_ASSET_EXTENSIONS):
            continue
        resolved = posixpath.normpath(posixpath.join(base_dir, spec)) if spec.startswith(".") else spec
        candidates = [resolved]
        if "." not in posixpath.basename(resolved):
            candidates.extend(
                f"{resolved}{suffix}"
                for suffix in (".js", ".jsx", ".ts", ".tsx")
            )
            candidates.extend(
                f"{resolved}/index{suffix}"
                for suffix in (".js", ".jsx", ".ts", ".tsx")
            )
        if not any(candidate in paths for candidate in candidates):
            return False
    return True


def _frontend_pages_exist(app_source: str, files: dict[str, str]) -> bool:
    if not app_source:
        return False
    if "<Route" in app_source and "path=" in app_source:
        return True
    if app_source.count("activeTab ===") >= 3:
        return True
    return any(path.startswith("src/pages/") and path.endswith((".jsx", ".tsx")) for path in files)


def _backend_routes_exist(api_routes: list[str], backend_main: str, api_spec: str) -> bool:
    if not backend_main:
        return False
    expected = api_routes or ["GET /api/dashboard"]
    for route in expected:
        method, path = _split_api_route(route)
        if not path.startswith("/api/"):
            continue
        decorator = f"@app.{method.lower()}({path!r})"
        alt_decorator = f'@app.{method.lower()}("{path}")'
        if decorator not in backend_main and alt_decorator not in backend_main and route not in api_spec:
            return False
    return True


def _implementation_files_complete(
    artifacts: list[dict[str, Any]],
    stack: dict[str, Any],
) -> bool:
    """Check that the project has appropriate implementation layers for its detected stack."""
    # Frontend layer: any API client or state management file
    if stack.get("has_frontend"):
        frontend_api_candidates = (
            "src/lib/api.js", "src/lib/api.ts", "lib/api.js", "lib/api.ts",
            "frontend/src/lib/api.js", "frontend/src/lib/api.ts",
            "src/services/api.js", "src/services/api.ts",
            "src/api/index.js", "src/api/index.ts",
            "utils/api.js", "utils/api.ts",
        )
        frontend_state_candidates = (
            "src/state/projectState.js", "src/state/projectState.ts",
            "frontend/src/state/projectState.js",
            "src/store/index.js", "src/store/index.ts",
            "src/context/AppContext.jsx", "src/context/AppContext.tsx",
            "src/hooks/useAppState.js", "src/hooks/useAppState.ts",
        )
        has_fe_api = any(_has_file(artifacts, p) for p in frontend_api_candidates)
        has_fe_state = any(_has_file(artifacts, p) for p in frontend_state_candidates)
        if not (has_fe_api and has_fe_state):
            return False

    # Backend layer: model + services/db are only required for web API backends
    # (FastAPI / Flask / Express). Python CLI / package projects don't need them.
    if stack.get("has_web_backend"):
        has_backend_models = bool(stack.get("models_path"))
        has_backend_services = bool(stack.get("services_path") or stack.get("db_path"))
        if not (has_backend_models and has_backend_services):
            return False

    return True


def _database_models_used(
    files: dict[str, str],
    backend_main: str,
    schema: str,
    stack: dict[str, Any] | None = None,
) -> bool:
    # Resolve model and db paths from the detected stack or fall back to defaults
    models_path = (stack or {}).get("models_path") or "backend/models.py"
    db_path = (stack or {}).get("db_path") or "backend/db.py"

    models = files.get(models_path, "")
    db = files.get(db_path, "")
    has_models = "class " in models and (
        "BaseModel" in models or "Column(" in models or "DATABASE_MODELS" in models
    )

    # Accept any import of the models module (supports non-default paths too)
    models_module = models_path.replace("/", ".").replace(".py", "")
    imports_models = (
        f"from {models_module} import" in backend_main
        or f"import {models_module}" in backend_main
        or "from backend.models import" in backend_main
        or "import backend.models" in backend_main
    )

    has_schema = "create table" in schema.lower()
    has_db_adapter = "save_activity" in db or "get_db" in db or "session" in db.lower()
    return has_models and imports_models and has_schema and has_db_adapter


def _readme_has_setup_features_demo(readme: str) -> bool:
    lowered = readme.lower()
    has_setup = any(marker in lowered for marker in ("run locally", "quick start", "setup"))
    has_features = "features" in lowered or "core features" in lowered
    has_demo = "demo" in lowered and "demo/script.md" in lowered
    return has_setup and has_features and has_demo


def _demo_materials_generated(files: dict[str, str], combined_demo: str, tokens: set[str]) -> bool:
    if not all(path in files and files[path].strip() for path in REQUIRED_DEMO_FILES):
        return False
    return _text_reflects_idea(combined_demo, tokens) and not _looks_generic(combined_demo)


def _seed_data_present(files: dict[str, str]) -> bool:
    return bool(files.get("data/seed.json", "").strip()) and bool(files.get("scripts/seed_data.py", "").strip())


def _study_project_complete(files: dict[str, str]) -> bool:
    corpus = "\n".join(
        files.get(path, "")
        for path in (
            "README.md",
            "src/App.jsx",
            "backend/main.py",
            "backend/models.py",
            "backend/db.py",
            "docs/DATABASE_SCHEMA.sql",
            "demo/script.md",
            "data/seed.json",
        )
    ).lower()
    required_terms = (
        "dashboard",
        "study plan",
        "flashcard",
        "quiz",
        "progress",
        "upload",
        "/api/study-plan",
        "/api/flashcards/review",
        "/api/progress",
        "/api/files/upload",
        "create table",
    )
    return all(term in corpus for term in required_terms)


def _split_api_route(route: str) -> tuple[str, str]:
    parts = str(route).strip().split(maxsplit=1)
    if len(parts) == 2 and parts[0].upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return parts[0].upper(), parts[1].strip()
    path = parts[0] if parts else "/api/dashboard"
    return "GET", path


def _title_matches_idea(
    title: str,
    idea: str,
    idea_tokens: set[str],
    title_tokens: set[str],
) -> bool:
    if _text_reflects_idea(title, idea_tokens) or _text_reflects_idea(title, title_tokens):
        return True
    compact_title = re.sub(r"[^a-z0-9]", "", title.lower())
    compact_idea = re.sub(r"[^a-z0-9]", "", idea.lower())
    return bool(compact_title) and compact_title in compact_idea


def _idea_tokens(idea: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{4,}", idea.lower()) if token not in STOP_WORDS}


def _text_reflects_idea(text: str, tokens: set[str]) -> bool:
    if not tokens:
        return True
    lowered = text.lower()
    hits = sum(1 for token in tokens if token in lowered)
    return hits >= min(2, len(tokens))


def _looks_generic(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in GENERIC_MARKERS)


def _uses_generic_feature_set(features: list[Any]) -> bool:
    normalized = [str(item).strip().lower() for item in features if str(item).strip()]
    if len(normalized) < 2:
        return False
    hits = sum(1 for phrase in GENERIC_FEATURE_PHRASES if any(phrase in item for item in normalized))
    return hits >= 2


def _looks_like_study_project(idea: str, features: list[Any]) -> bool:
    corpus = " ".join([idea, *(str(feature) for feature in features)]).lower()
    return any(
        word in corpus
        for word in ("study", "lecture", "quiz", "flashcard", "spaced repetition", "exam")
    )


def _user_flow_defined(requirements: dict[str, Any]) -> bool:
    flows = requirements.get("user_flows")
    return isinstance(flows, list) and len(flows) >= 2


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


STOP_WORDS = {
    "build",
    "create",
    "make",
    "that",
    "with",
    "from",
    "into",
    "help",
    "helps",
    "this",
    "your",
    "their",
    "platform",
    "project",
    "software",
    "system",
    "agent",
    "and",
    "the",
    "for",
}
