from __future__ import annotations

import json
import re
from typing import Any

from agent.project_depth import (
    depth_profile,
    enrich_project_requirements,
    project_collection_route,
    project_tabs,
    title_from_idea,
)


def build_project_artifacts(
    *,
    idea: str,
    title: str | None,
    resolved_stack: str,
    architecture_plan: dict[str, Any] | None = None,
    repo_plan: dict[str, Any] | None = None,
    source_warnings: list[dict[str, str]] | None = None,
    target_users: str | None = None,
    required_features: list[str] | None = None,
    tech_stack_preference: str | None = None,
    project_requirements: dict[str, Any] | None = None,
    mvp_scope: dict[str, Any] | None = None,
    target_platform: str | None = None,
    api_routes: list[str] | None = None,
    is_hackathon_mode: bool = False,
) -> list[dict[str, str]]:
    """Create a complete generated project package from the orchestration plan."""

    plan = architecture_plan or repo_plan or {}
    requirements = enrich_project_requirements(
        project_requirements or mvp_scope or {},
        idea=idea,
        intake={
            "requiredFeatures": required_features or [],
            "targetUsers": target_users,
            "techStackPreference": tech_stack_preference,
        },
    )
    project_title = _clean_text(title or "") or title_from_idea(idea)
    slug = _slugify(project_title)
    stack = tech_stack_preference or _selected_stack(plan, resolved_stack)
    warnings = _warning_lines(source_warnings or [])
    features = _feature_list(requirements, required_features)
    advanced_features = _string_list(requirements.get("advanced_features"))
    personas = _string_list(requirements.get("user_personas")) or ["Primary user"]
    user_flows = requirements.get("user_flows") if isinstance(requirements.get("user_flows"), list) else []
    archetype = str(requirements.get("project_archetype") or "workflow")
    depth = str(requirements.get("project_depth") or "Advanced Project")
    # Explicit parameter takes precedence over requirements-derived platform
    _req_platform = str(requirements.get("target_platform") or "web app")
    target_platform = str(target_platform or _req_platform)
    route = project_collection_route(archetype)
    tabs = project_tabs(archetype, idea)
    is_study = _looks_like_study_project(idea, features)
    # Explicit api_routes parameter takes precedence over requirements-derived routes
    _req_routes = _string_list(requirements.get("api_routes"))
    if api_routes is not None:
        api_routes = list(api_routes)
    elif _req_routes:
        api_routes = _req_routes
    else:
        api_routes = ["GET /health"]

    # Platform resolver — determines which file sets are included
    project_category = str(requirements.get("project_category") or "").lower()
    platform_lower = (target_platform or "web app").lower().strip()
    is_api_only = (
        platform_lower in ("api", "api only", "api service", "backend only")
        or project_category == "api_service"
    )
    is_cli = (
        platform_lower in ("cli", "cli tool", "terminal", "command line", "desktop tool")
        or project_category == "cli_tool"
    )
    is_extension = (
        platform_lower in ("browser extension", "extension", "chrome extension")
        or project_category == "browser_extension"
    )
    is_mobile = (
        platform_lower in ("mobile app", "mobile", "ios app", "android app")
        or "react native" in platform_lower
        or project_category == "mobile_app"
    )
    is_portfolio = (
        platform_lower in ("portfolio", "portfolio website", "static site")
        or "portfolio" in idea.lower()
        or project_category == "portfolio_website"
    )
    is_web = not (is_api_only or is_cli or is_extension or is_mobile or is_portfolio)

    # Common docs/demo files present in every platform type
    common_files: list[dict[str, str]] = [
        {
            "name": "README.md",
            "kind": "markdown",
            "summary": "Full project overview, setup, architecture, env guide, testing, and deployment notes.",
            "content": _readme(
                project_title=project_title,
                idea=idea,
                stack=stack,
                depth=depth,
                target_platform=target_platform,
                personas=personas,
                features=features,
                advanced_features=advanced_features,
                api_routes=api_routes,
                user_flows=user_flows,
                warnings=warnings,
            ),
        },
        {
            "name": "data/seed.json",
            "kind": "json",
            "summary": "Project-specific seed/sample data for local demos.",
            "content": _seed_json(project_title, idea, features, user_flows, is_study),
        },
        {
            "name": "docs/PROJECT_PLAN.md",
            "kind": "markdown",
            "summary": "Expanded product plan, features, milestones, and success criteria.",
            "content": _project_plan(project_title, idea, requirements, features, advanced_features),
        },
        {
            "name": "docs/ARCHITECTURE.md",
            "kind": "markdown",
            "summary": "Frontend, backend, data, auth, integration, testing, and deployment architecture.",
            "content": _architecture(project_title, idea, stack, requirements, plan, warnings),
        },
        {
            "name": "docs/TESTING_STRATEGY.md",
            "kind": "markdown",
            "summary": "Unit, API, frontend, validation, and build verification strategy.",
            "content": _testing_strategy(project_title, depth),
        },
        {
            "name": "docs/DEPLOY.md",
            "kind": "markdown",
            "summary": "Deployment guide for frontend, backend, database, and environment variables.",
            "content": _deploy_doc(project_title),
        },
        {
            "name": "docs/AGENT_LOG.md",
            "kind": "markdown",
            "summary": "Visible orchestration log with agent responsibilities and generation decisions.",
            "content": _agent_log(project_title, requirements, plan, warnings),
        },
        {
            "name": "docs/BUILD_LOG.md",
            "kind": "markdown",
            "summary": "Build and validation log for the generated codebase.",
            "content": _build_log(project_title, stack, depth, features, warnings),
        },
        {
            "name": "docs/KNOWN_LIMITATIONS.md",
            "kind": "markdown",
            "summary": "Known limitations and future improvements.",
            "content": _limitations(project_title),
        },
        {
            "name": "docs/WALKTHROUGH.md",
            "kind": "markdown",
            "summary": "End-to-end product walkthrough and demo flow.",
            "content": _walkthrough(project_title, idea, features, user_flows, api_routes, is_study),
        },
        {
            "name": ".env.example",
            "kind": "text",
            "summary": "Safe placeholder environment file.",
            "content": _env_example(project_title),
        },
    ]

    if is_hackathon_mode:
        common_files.extend(
            [
                {
                    "name": "docs/HACKATHON_SUBMISSION.md",
                    "kind": "markdown",
                    "summary": "Hackathon submission summary with problem, solution, tech, demo flow, and proof.",
                    "content": _hackathon_submission(project_title, idea, stack, features, api_routes, is_study),
                },
                {
                    "name": "demo/script.md",
                    "kind": "markdown",
                    "summary": "Timestamped demo video script for the generated product.",
                    "content": _demo_script(project_title, idea, features, user_flows, api_routes, is_study),
                },
                {
                    "name": "demo/storyboard.md",
                    "kind": "markdown",
                    "summary": "Shot-by-shot storyboard for recording a hackathon demo.",
                    "content": _storyboard(project_title, features, user_flows, api_routes, is_study),
                },
                {
                    "name": "demo/demo_walkthrough.md",
                    "kind": "markdown",
                    "summary": "Click-by-click local demo walkthrough.",
                    "content": _walkthrough(project_title, idea, features, user_flows, api_routes, is_study),
                },
                {
                    "name": "demo/video_outline.md",
                    "kind": "markdown",
                    "summary": "Recording outline for the final demo video.",
                    "content": _video_outline(project_title, idea, features, api_routes, is_study),
                },
                {
                    "name": "demo/voiceover.md",
                    "kind": "markdown",
                    "summary": "Optional voiceover copy for the demo video.",
                    "content": _voiceover(project_title, idea, features, is_study),
                },
                {
                    "name": "demo/demo_script.md",
                    "kind": "markdown",
                    "summary": "Backward-compatible copy of the judge-facing demo script.",
                    "content": _demo_script(project_title, idea, features, user_flows, api_routes, is_study),
                },
            ]
        )

    if requirements.get("database_required") is False:
        common_files = [item for item in common_files if item["name"] != "data/seed.json"]

    # Platform-specific file sets
    platform_files: list[dict[str, str]] = []
    needs_database = bool(requirements.get("database_required", True))

    if is_mobile:
        platform_files += [
            {
                "name": "package.json",
                "kind": "json",
                "summary": "React Native app metadata and scripts.",
                "content": _mobile_package_json(slug, project_title),
            },
            {
                "name": "App.tsx",
                "kind": "typescript",
                "summary": "React Native root component.",
                "content": _mobile_app_tsx(project_title, idea, features),
            },
            {
                "name": "index.js",
                "kind": "javascript",
                "summary": "React Native entrypoint.",
                "content": _mobile_index_js(),
            },
            {
                "name": "src/lib/api.ts",
                "kind": "typescript",
                "summary": "API client for the mobile app.",
                "content": _api_client(api_routes).replace("import.meta.env.VITE_API_BASE_URL", "process.env.EXPO_PUBLIC_API_BASE_URL"),
            },
        ]
    elif is_portfolio:
        platform_files += [
            {
                "name": "frontend/index.html",
                "kind": "html",
                "summary": "Portfolio site HTML shell.",
                "content": _index_html(project_title).replace('id="root"', 'id="app"'),
            },
            {
                "name": "frontend/src/main.js",
                "kind": "javascript",
                "summary": "Portfolio site entrypoint.",
                "content": "document.getElementById('app').innerHTML = '<h1>Portfolio</h1>';\n",
            },
            {
                "name": "frontend/src/styles.css",
                "kind": "css",
                "summary": "Portfolio styling.",
                "content": _css(),
            },
        ]
    elif is_web:
        platform_files += [
            {
                "name": "package.json",
                "kind": "json",
                "summary": "Frontend scripts, build command, and test dependencies.",
                "content": _package_json(slug),
            },
            {
                "name": "index.html",
                "kind": "html",
                "summary": "Frontend HTML shell.",
                "content": _index_html(project_title),
            },
            {
                "name": "src/main.jsx",
                "kind": "javascript",
                "summary": "React entrypoint.",
                "content": _main_jsx(),
            },
            {
                "name": "src/App.jsx",
                "kind": "javascript",
                "summary": "Full project studio UI with auth, upload, generation, review, and dashboard flows.",
                "content": _react_app(
                    project_title=project_title,
                    idea=idea,
                    features=features,
                    advanced_features=advanced_features,
                    personas=personas,
                    user_flows=user_flows,
                    api_routes=api_routes,
                    tabs=tabs,
                    route=route,
                    is_study=is_study,
                ),
            },
            {
                "name": "src/lib/api.js",
                "kind": "javascript",
                "summary": "Typed API client helpers for the generated backend routes.",
                "content": _api_client(api_routes),
            },
            {
                "name": "src/state/projectState.js",
                "kind": "javascript",
                "summary": "Domain seed state used by the generated UI and tests.",
                "content": _frontend_state(project_title, features, user_flows, is_study),
            },
            {
                "name": "src/styles.css",
                "kind": "css",
                "summary": "Responsive application styling for a production-style tool surface.",
                "content": _css(),
            },
            {
                "name": "backend/main.py",
                "kind": "python",
                "summary": "FastAPI app with auth, upload, summary, quiz, flashcard, dashboard, and health routes.",
                "content": _backend_main(
                    project_title, idea, features, api_routes, is_study, needs_database
                ),
            },
            {
                "name": "backend/models.py",
                "kind": "python",
                "summary": "Pydantic request and response models for generated API flows.",
                "content": _backend_models(project_title, features),
            },
            {
                "name": "backend/services.py",
                "kind": "python",
                "summary": "Business logic for the generated API routes.",
                "content": _backend_services(project_title, idea, features, is_study),
            },
            {
                "name": "requirements.txt",
                "kind": "text",
                "summary": "Backend runtime and test dependencies.",
                "content": "fastapi\nuvicorn[standard]\npydantic\npython-multipart\npytest\nhttpx\n",
            },
            {
                "name": "tests/test_backend.py",
                "kind": "python",
                "summary": "Generated API smoke tests for planned routes.",
                "content": _backend_tests(project_title, api_routes),
            },
            {
                "name": "docs/API_SPEC.md",
                "kind": "markdown",
                "summary": "API route plan with responsibilities and data flow.",
                "content": _api_spec(project_title, api_routes),
            },
        ]
        if needs_database:
            platform_files += [
                {
                    "name": "backend/db.py",
                    "kind": "python",
                    "summary": "SQLite-backed persistence adapter with Postgres-ready boundaries.",
                    "content": _backend_db(slug),
                },
                {
                    "name": "scripts/seed_data.py",
                    "kind": "python",
                    "summary": "Seed script that loads sample data through the generated persistence adapter.",
                    "content": _seed_script(),
                },
                {
                    "name": "docs/DATABASE_SCHEMA.sql",
                    "kind": "sql",
                    "summary": "Postgres/Supabase schema for the generated project.",
                    "content": _database_schema(slug, is_study),
                },
            ]

    elif is_api_only:
        platform_files += [
            {
                "name": "backend/main.py",
                "kind": "python",
                "summary": "FastAPI application exposing the planned API routes.",
                "content": _backend_main(
                    project_title, idea, features, api_routes, is_study, needs_database
                ),
            },
            {
                "name": "backend/models.py",
                "kind": "python",
                "summary": "Pydantic request and response models.",
                "content": _backend_models(project_title, features),
            },
            {
                "name": "backend/services.py",
                "kind": "python",
                "summary": "Business logic layer for the API service.",
                "content": _backend_services(project_title, idea, features, is_study),
            },
            {
                "name": "requirements.txt",
                "kind": "text",
                "summary": "API service runtime and test dependencies.",
                "content": "fastapi\nuvicorn[standard]\npydantic\npython-multipart\npytest\nhttpx\n",
            },
            {
                "name": "tests/test_api.py",
                "kind": "python",
                "summary": "API smoke tests for all generated routes.",
                "content": _backend_tests(project_title, api_routes),
            },
            {
                "name": "docs/API_SPEC.md",
                "kind": "markdown",
                "summary": "API route plan with responsibilities and data flow.",
                "content": _api_spec(project_title, api_routes),
            },
        ]
        if needs_database:
            platform_files += [
                {
                    "name": "backend/db.py",
                    "kind": "python",
                    "summary": "SQLite-backed persistence adapter with Postgres-ready boundaries.",
                    "content": _backend_db(slug),
                },
                {
                    "name": "docs/DATABASE_SCHEMA.sql",
                    "kind": "sql",
                    "summary": "Postgres/Supabase schema for the API service.",
                    "content": _database_schema(slug, is_study),
                },
            ]

    elif is_cli:
        platform_files += [
            {
                "name": "cli/__init__.py",
                "kind": "python",
                "summary": "CLI package init.",
                "content": f'"""Command-line interface for {project_title}."""\n',
            },
            {
                "name": "cli/main.py",
                "kind": "python",
                "summary": "CLI entrypoint built with Click.",
                "content": _cli_main(project_title, idea, features),
            },
            {
                "name": "pyproject.toml",
                "kind": "text",
                "summary": "Python project metadata and CLI entry point declaration.",
                "content": _pyproject_toml(slug, project_title),
            },
            {
                "name": "requirements.txt",
                "kind": "text",
                "summary": "CLI runtime and test dependencies.",
                "content": "click\nrich\npytest\n",
            },
            {
                "name": "tests/test_cli.py",
                "kind": "python",
                "summary": "CLI smoke tests using Click's test runner.",
                "content": _cli_tests(project_title),
            },
        ]

    elif is_extension:
        platform_files += [
            {
                "name": "manifest.json",
                "kind": "json",
                "summary": "Chrome Extension Manifest V3 configuration.",
                "content": _extension_manifest(project_title, slug),
            },
            {
                "name": "background.js",
                "kind": "javascript",
                "summary": "Service worker for the browser extension.",
                "content": _extension_background(project_title),
            },
            {
                "name": "popup.html",
                "kind": "html",
                "summary": "Extension popup HTML.",
                "content": _extension_popup_html(project_title),
            },
            {
                "name": "popup.js",
                "kind": "javascript",
                "summary": "Extension popup logic.",
                "content": _extension_popup_js(project_title, features),
            },
            {
                "name": "content.js",
                "kind": "javascript",
                "summary": "Content script injected into web pages.",
                "content": _extension_content_js(project_title),
            },
            {
                "name": "src/utils.js",
                "kind": "javascript",
                "summary": "Shared utility functions for the extension.",
                "content": _extension_utils(project_title),
            },
        ]

    files = platform_files + common_files
    return files


def merge_with_project_artifacts(
    artifacts: list[dict[str, Any]],
    *,
    idea: str,
    title: str | None,
    resolved_stack: str,
    architecture_plan: dict[str, Any] | None = None,
    repo_plan: dict[str, Any] | None = None,
    source_warnings: list[dict[str, str]] | None = None,
    target_users: str | None = None,
    required_features: list[str] | None = None,
    tech_stack_preference: str | None = None,
    project_requirements: dict[str, Any] | None = None,
    mvp_scope: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        name = str(artifact.get("name") or "").strip()
        if not name or name.endswith("/") or name.split("/")[-1] == ".env":
            continue
        content = artifact.get("content")
        if content is None:
            continue
        merged[name] = {
            "name": name,
            "kind": str(artifact.get("kind") or _kind_from_path(name)),
            "summary": str(artifact.get("summary") or "Generated by configured LLM."),
            "content": content if isinstance(content, str) else json.dumps(content, indent=2),
        }

    gap_fill = build_project_artifacts(
        idea=idea,
        title=title,
        resolved_stack=resolved_stack,
        architecture_plan=architecture_plan,
        repo_plan=repo_plan,
        source_warnings=source_warnings,
        target_users=target_users,
        required_features=required_features,
        tech_stack_preference=tech_stack_preference,
        project_requirements=project_requirements,
        mvp_scope=mvp_scope,
    )
    for artifact in gap_fill:
        merged.setdefault(artifact["name"], artifact)
    return [merged[path] for path in sorted(merged)]


# ---------------------------------------------------------------------------
# CLI scaffold helpers
# ---------------------------------------------------------------------------

def _mobile_package_json(slug: str, project_title: str) -> str:
    return json.dumps(
        {
            "name": slug,
            "version": "0.1.0",
            "private": True,
            "main": "index.js",
            "scripts": {"start": "expo start", "android": "expo start --android", "ios": "expo start --ios"},
            "dependencies": {"expo": "~51.0.0", "react": "18.2.0", "react-native": "0.74.0"},
            "description": project_title,
        },
        indent=2,
    )


def _mobile_app_tsx(project_title: str, idea: str, features: list[str]) -> str:
    feature_line = features[0] if features else idea
    return (
        "import { SafeAreaView, Text, View, StyleSheet } from 'react-native';\n\n"
        f"const TITLE = {json.dumps(project_title)};\n"
        f"const IDEA = {json.dumps(idea)};\n"
        f"const FEATURE = {json.dumps(feature_line)};\n\n"
        "export default function App() {\n"
        "  return (\n"
        "    <SafeAreaView style={styles.container}>\n"
        "      <Text style={styles.title}>{TITLE}</Text>\n"
        "      <Text style={styles.subtitle}>{FEATURE}</Text>\n"
        "    </SafeAreaView>\n"
        "  );\n"
        "}\n\n"
        "const styles = StyleSheet.create({ container: { flex: 1, padding: 24 }, title: { fontSize: 24, fontWeight: '700' }, subtitle: { marginTop: 8 } });\n"
    )


def _mobile_index_js() -> str:
    return (
        "import { registerRootComponent } from 'expo';\n"
        "import App from './App';\n\n"
        "registerRootComponent(App);\n"
    )


def _cli_main(project_title: str, idea: str, features: list[str]) -> str:
    feat_items = "\n".join(f'    click.echo("  - {f}")' for f in features[:6]) or '    click.echo("  - No features specified.")'
    return (
        f'"""CLI entrypoint for {project_title}.\n\n{idea}\n"""\n\n'
        "import click\n"
        "from rich.console import Console\n\n"
        "console = Console()\n\n\n"
        "@click.group()\n"
        "@click.version_option(version='0.1.0')\n"
        "def cli():\n"
        f'    """Command-line interface for {project_title}."""\n\n\n'
        "@cli.command()\n"
        "def info():\n"
        f'    """Show project information."""\n'
        f'    console.print("[bold green]{project_title}[/bold green]")\n'
        f'    console.print("{idea}")\n'
        "    click.echo(\"\\nFeatures:\")\n"
        f"{feat_items}\n\n\n"
        "@cli.command()\n"
        "@click.argument('input', type=click.Path(exists=True), required=False)\n"
        "def run(input):\n"
        '    """Run the primary workflow."""\n'
        '    console.print("[bold]Running workflow...[/bold]")\n'
        '    if input:\n'
        '        console.print(f"Processing: {input}")\n'
        '    console.print("[green]Done.[/green]")\n\n\n'
        "if __name__ == '__main__':\n"
        "    cli()\n"
    )


def _pyproject_toml(slug: str, project_title: str) -> str:
    safe_slug = slug.replace("-", "_")
    return (
        "[build-system]\n"
        'requires = ["setuptools>=68"]\n'
        'build-backend = "setuptools.backends.legacy:build"\n\n'
        "[project]\n"
        f'name = "{slug}"\n'
        'version = "0.1.0"\n'
        f'description = "{project_title} CLI tool"\n'
        'requires-python = ">=3.11"\n'
        'dependencies = ["click", "rich"]\n\n'
        "[project.scripts]\n"
        f'{slug} = "{safe_slug}.cli.main:cli"\n'
    )


def _cli_tests(project_title: str) -> str:
    return (
        "from click.testing import CliRunner\n\n"
        "from cli.main import cli\n\n\n"
        "def test_cli_info():\n"
        "    runner = CliRunner()\n"
        "    result = runner.invoke(cli, ['info'])\n"
        "    assert result.exit_code == 0\n"
        f"    assert {project_title!r} in result.output or result.output\n\n\n"
        "def test_cli_run_no_input():\n"
        "    runner = CliRunner()\n"
        "    result = runner.invoke(cli, ['run'])\n"
        "    assert result.exit_code == 0\n"
    )


# ---------------------------------------------------------------------------
# Browser extension scaffold helpers
# ---------------------------------------------------------------------------

def _extension_manifest(project_title: str, slug: str) -> str:
    return json.dumps({
        "manifest_version": 3,
        "name": project_title,
        "version": "0.1.0",
        "description": f"Browser extension: {project_title}",
        "permissions": ["activeTab", "storage", "scripting"],
        "background": {"service_worker": "background.js"},
        "action": {
            "default_popup": "popup.html",
            "default_title": project_title,
        },
        "content_scripts": [
            {
                "matches": ["<all_urls>"],
                "js": ["content.js"],
                "run_at": "document_idle",
            }
        ],
    }, indent=2) + "\n"


def _extension_background(project_title: str) -> str:
    return (
        f"// Background service worker for {project_title}\n\n"
        "chrome.runtime.onInstalled.addListener(() => {\n"
        f"  console.log('{project_title} installed.');\n"
        "});\n\n"
        "chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {\n"
        "  if (message.type === 'GET_STATE') {\n"
        "    chrome.storage.local.get('state', (data) => sendResponse(data.state || {}));\n"
        "    return true; // async\n"
        "  }\n"
        "  if (message.type === 'SET_STATE') {\n"
        "    chrome.storage.local.set({ state: message.payload }, () => sendResponse({ ok: true }));\n"
        "    return true;\n"
        "  }\n"
        "});\n"
    )


def _extension_popup_html(project_title: str) -> str:
    safe_title = _html_escape(project_title)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="UTF-8" />\n'
        f"  <title>{safe_title}</title>\n"
        '  <style>\n'
        '    body { font-family: system-ui, sans-serif; width: 320px; padding: 16px; margin: 0; }\n'
        '    h1 { font-size: 18px; margin: 0 0 12px; }\n'
        '    button { background: #0f766e; color: #fff; border: 0; border-radius: 6px; padding: 8px 14px; cursor: pointer; font-weight: 700; }\n'
        '    #status { margin-top: 12px; font-size: 13px; color: #4b5c66; }\n'
        '  </style>\n'
        "</head>\n"
        "<body>\n"
        f"  <h1>{safe_title}</h1>\n"
        '  <button id="run">Run</button>\n'
        '  <div id="status">Ready.</div>\n'
        '  <script src="popup.js"></script>\n'
        "</body>\n"
        "</html>\n"
    )


def _extension_popup_js(project_title: str, features: list[str]) -> str:
    feat_list = ", ".join(repr(f) for f in features[:4]) or "'No features yet'"
    return (
        f"// Popup script for {project_title}\n\n"
        f"const FEATURES = [{feat_list}];\n\n"
        "document.getElementById('run').addEventListener('click', () => {\n"
        "  const status = document.getElementById('status');\n"
        "  status.textContent = 'Running...';\n"
        "  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {\n"
        "    chrome.tabs.sendMessage(tabs[0].id, { type: 'RUN', features: FEATURES }, (response) => {\n"
        "      status.textContent = response ? response.message : 'Done.';\n"
        "    });\n"
        "  });\n"
        "});\n"
    )


def _extension_content_js(project_title: str) -> str:
    return (
        f"// Content script for {project_title}\n\n"
        "chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {\n"
        "  if (message.type === 'RUN') {\n"
        "    const result = runExtension(message.features || []);\n"
        "    sendResponse({ message: result });\n"
        "  }\n"
        "});\n\n"
        "function runExtension(features) {\n"
        "  // TODO: implement extension logic for the active page\n"
        "  console.log('Extension activated with features:', features);\n"
        "  return `Processed ${document.querySelectorAll('*').length} elements.`;\n"
        "}\n"
    )


def _extension_utils(project_title: str) -> str:
    return (
        f"// Shared utilities for {project_title}\n\n"
        "export function getStorage(key) {\n"
        "  return new Promise((resolve) => chrome.storage.local.get(key, (data) => resolve(data[key])));\n"
        "}\n\n"
        "export function setStorage(key, value) {\n"
        "  return new Promise((resolve) => chrome.storage.local.set({ [key]: value }, resolve));\n"
        "}\n\n"
        "export function sendToBackground(type, payload = {}) {\n"
        "  return new Promise((resolve) => chrome.runtime.sendMessage({ type, payload }, resolve));\n"
        "}\n"
    )


def _readme(
    *,
    project_title: str,
    idea: str,
    stack: str,
    depth: str,
    target_platform: str,
    personas: list[str],
    features: list[str],
    advanced_features: list[str],
    api_routes: list[str],
    user_flows: list[dict[str, Any]],
    warnings: list[str],
) -> str:
    return (
        f"# {project_title}\n\n"
        f"{idea}\n\n"
        f"Generated as a **{depth}** for a **{target_platform}**. The repository is structured as a complete, hackathon-ready full-stack project with authentication, polished UI flows, database-backed data, seed/sample data, API contracts, tests, documentation, demo video materials, and deployment notes.\n\n"
        "## Target Users\n\n"
        + _markdown_items(personas)
        + "\n## Core Features\n\n"
        + _markdown_items(features)
        + "\n## Advanced Features\n\n"
        + _markdown_items(advanced_features or ["Production-ready extension points", "Operational logs", "Deployment readiness"])
        + "\n## Tech Stack\n\n"
        f"{stack}\n\n"
        "## API Plan\n\n"
        + _markdown_items(api_routes)
        + "\n## Demo\n\n"
        "Use the demo materials in `demo/` to record or present the project:\n\n"
        "- `demo/script.md` - timestamped spoken script for the full product flow.\n"
        "- `demo/storyboard.md` - shot-by-shot recording plan tied to real screens and routes.\n"
        "- `demo/demo_walkthrough.md` - click-by-click local walkthrough.\n"
        "- `demo/video_outline.md` - concise outline for a hackathon submission video.\n"
        "- `demo/voiceover.md` - optional narration copy.\n\n"
        "Demo flow:\n\n"
        + _flow_items(user_flows)
        + "\n## Run Locally\n\n"
        "```bash\nnpm install\nnpm run dev\n```\n\n"
        "In another terminal:\n\n"
        "```bash\npip install -r requirements.txt\nuvicorn backend.main:app --reload\n```\n\n"
        "## Test\n\n"
        "```bash\npytest\nnpm run build\n```\n\n"
        "## Seed Data\n\n"
        "Sample data lives in `data/seed.json`. Run `python scripts/seed_data.py` after installing backend dependencies to load demo activity into the local database.\n\n"
        "## Hackathon Submission\n\n"
        "See `docs/HACKATHON_SUBMISSION.md` for the problem statement, differentiators, technical proof, and final judging summary.\n\n"
        "## Environment\n\n"
        "Copy `.env.example` and set backend-only secrets in the backend deployment environment. Never commit real `.env` files.\n"
        + _warning_section(warnings)
    )


def _package_json(slug: str) -> str:
    return json.dumps(
        {
            "name": slug,
            "version": "0.1.0",
            "private": True,
            "type": "module",
            "scripts": {
                "dev": "vite --host 0.0.0.0",
                "build": "vite build",
                "preview": "vite preview",
            },
            "dependencies": {
                "@vitejs/plugin-react": "^6.0.0",
                "vite": "^8.0.0",
                "react": "^19.0.0",
                "react-dom": "^19.0.0",
            },
            "devDependencies": {},
        },
        indent=2,
    ) + "\n"


def _index_html(project_title: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "  <head>\n"
        '    <meta charset="UTF-8" />\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        f"    <title>{_html_escape(project_title)}</title>\n"
        "  </head>\n"
        "  <body>\n"
        '    <div id="root"></div>\n'
        '    <script type="module" src="/src/main.jsx"></script>\n'
        "  </body>\n"
        "</html>\n"
    )


def _main_jsx() -> str:
    return (
        "import React from 'react';\n"
        "import { createRoot } from 'react-dom/client';\n"
        "import App from './App.jsx';\n"
        "import './styles.css';\n\n"
        "createRoot(document.getElementById('root')).render(\n"
        "  <React.StrictMode>\n"
        "    <App />\n"
        "  </React.StrictMode>,\n"
        ");\n"
    )


def _react_app(
    *,
    project_title: str,
    idea: str,
    features: list[str],
    advanced_features: list[str],
    personas: list[str],
    user_flows: list[dict[str, Any]],
    api_routes: list[str],
    tabs: list[str],
    route: str,
    is_study: bool,
) -> str:
    return (
        "import { useMemo, useState } from 'react';\n"
        "import { seedAssets, reviewQueue, dashboardMetrics } from './state/projectState.js';\n"
        "import { createUpload, generateQuiz, getDashboard } from './lib/api.js';\n\n"
        f"const projectTitle = {json.dumps(project_title)};\n"
        f"const idea = {json.dumps(idea)};\n"
        f"const features = {json.dumps(features, indent=2)};\n"
        f"const advancedFeatures = {json.dumps(advanced_features, indent=2)};\n"
        f"const personas = {json.dumps(personas, indent=2)};\n"
        f"const userFlows = {json.dumps(user_flows, indent=2)};\n"
        f"const apiRoutes = {json.dumps(api_routes, indent=2)};\n"
        f"const tabs = {json.dumps(tabs)};\n"
        f"const collectionRoute = {json.dumps(route)};\n"
        f"const isStudyProject = {json.dumps(is_study)};\n\n"
        "export default function App() {\n"
        "  const [activeTab, setActiveTab] = useState(tabs[0]);\n"
        "  const [session, setSession] = useState({ name: 'Avery Student', role: 'owner' });\n"
        "  const [noteText, setNoteText] = useState('Photosynthesis lecture: spaced repetition works best when reviews are scheduled right before forgetting.');\n"
        "  const [generated, setGenerated] = useState(null);\n"
        "  const [status, setStatus] = useState('Ready');\n"
        "  const metrics = useMemo(() => dashboardMetrics, []);\n\n"
        "  async function handleGenerate() {\n"
        "    setStatus('Generating');\n"
        "    const upload = await createUpload({ title: 'Lecture notes', content: noteText, route: collectionRoute });\n"
        "    const quiz = await generateQuiz({ source_id: upload.id, content: noteText });\n"
        "    setGenerated({ upload, quiz });\n"
        "    setStatus('Generated');\n"
        "  }\n\n"
        "  async function refreshDashboard() {\n"
        "    setStatus('Refreshing dashboard');\n"
        "    const dashboard = await getDashboard();\n"
        "    setGenerated((current) => ({ ...(current || {}), dashboard }));\n"
        "    setStatus('Dashboard refreshed');\n"
        "  }\n\n"
        "  return (\n"
        "    <main className=\"appShell\">\n"
        "      <header className=\"topbar\">\n"
        "        <div>\n"
        "          <p className=\"eyebrow\">Full-Stack Generated Project</p>\n"
        "          <h1>{projectTitle}</h1>\n"
        "          <p className=\"lede\">{idea}</p>\n"
        "        </div>\n"
        "        <div className=\"sessionCard\">\n"
        "          <span>Signed in</span>\n"
        "          <strong>{session.name}</strong>\n"
        "          <button type=\"button\" onClick={() => setSession({ name: 'Morgan Admin', role: 'admin' })}>Switch role</button>\n"
        "        </div>\n"
        "      </header>\n"
        "      <nav className=\"tabs\">{tabs.map((tab) => <button key={tab} type=\"button\" className={activeTab === tab ? 'active' : ''} onClick={() => setActiveTab(tab)}>{tab}</button>)}</nav>\n"
        "      {activeTab === tabs[0] && <section className=\"grid\"><ProjectBrief personas={personas} features={features} apiRoutes={apiRoutes} /><Metrics metrics={metrics} /></section>}\n"
        "      {activeTab === tabs[1] && <section className=\"workspace\"><textarea value={noteText} onChange={(event) => setNoteText(event.target.value)} rows={8} /><div className=\"actions\"><button type=\"button\" onClick={handleGenerate}>{isStudyProject ? 'Generate study assets' : 'Generate workflow assets'}</button><button type=\"button\" onClick={refreshDashboard}>Refresh dashboard</button></div><p className=\"status\">{status}</p></section>}\n"
        "      {activeTab === tabs[2] && <section className=\"grid\"><ReviewQueue generated={generated} /><Advanced features={advancedFeatures} /></section>}\n"
        "      {activeTab === tabs[3] && <section className=\"dashboard\"><FlowList flows={userFlows} /><AssetTable /></section>}\n"
        "    </main>\n"
        "  );\n"
        "}\n\n"
        "function ProjectBrief({ personas, features, apiRoutes }) {\n"
        "  return <article className=\"panel\"><h2>Product System</h2><p>Built for {personas.join(', ')}.</p><ul>{features.slice(0, 8).map((feature) => <li key={feature}>{feature}</li>)}</ul><h3>API routes</h3><ul>{apiRoutes.map((route) => <li key={route}>{route}</li>)}</ul></article>;\n"
        "}\n\n"
        "function Metrics({ metrics }) {\n"
        "  return <article className=\"panel metrics\"><h2>Readiness Dashboard</h2>{metrics.map((metric) => <div key={metric.label} className=\"metric\"><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.detail}</small></div>)}</article>;\n"
        "}\n\n"
        "function ReviewQueue({ generated }) {\n"
        "  const quizItems = generated?.quiz?.questions || reviewQueue;\n"
        "  return <article className=\"panel\"><h2>Generated Review</h2><ul>{quizItems.map((item) => <li key={item.id || item.question}>{item.question || item.prompt}<span>{item.answer || item.due}</span></li>)}</ul></article>;\n"
        "}\n\n"
        "function Advanced({ features }) {\n"
        "  return <article className=\"panel\"><h2>Advanced System Features</h2><ul>{features.map((feature) => <li key={feature}>{feature}</li>)}</ul></article>;\n"
        "}\n\n"
        "function FlowList({ flows }) {\n"
        "  return <article className=\"panel\"><h2>User Flow</h2>{flows.map((flow) => <div key={flow.step} className=\"flow\"><strong>{flow.screen}</strong><span>{flow.action}</span><code>{flow.api || 'UI'}</code></div>)}</article>;\n"
        "}\n\n"
        "function AssetTable() {\n"
        "  return <article className=\"panel\"><h2>Generated Assets</h2>{seedAssets.map((asset) => <div key={asset.id} className=\"asset\"><span>{asset.type}</span><strong>{asset.title}</strong><em>{asset.status}</em></div>)}</article>;\n"
        "}\n"
    )


def _api_client(api_routes: list[str]) -> str:
    """Generate API client functions from the actual planned routes."""

    def route_to_fn(route: str) -> tuple[str, str, str]:
        parts = route.strip().split(None, 1)
        method = parts[0].lower() if parts else "get"
        path = parts[1] if len(parts) > 1 else "/api/health"
        if path.startswith("/api/"):
            slug = path[len("/api/") :]
        elif path.startswith("/"):
            slug = path[1:]
        else:
            slug = path
        segments = [segment for segment in re.split(r"[/_{}-]+", slug) if segment]
        if not segments:
            segments = ["health"]
        camel = segments[0].lower() + "".join(segment.capitalize() for segment in segments[1:])
        fn_name = method + camel[0].upper() + camel[1:]
        return method, path, fn_name

    if not api_routes:
        api_routes = ["GET /health"]

    fns = []
    seen: set[str] = set()
    for route in api_routes[:8]:  # cap at 8 to keep file size reasonable
        method, path, fn_name = route_to_fn(route)
        if fn_name in seen:
            continue
        seen.add(fn_name)
        if method in ("post", "put", "patch"):
            fns.append(
                f"export async function {fn_name}(data) {{\n"
                f"  const r = await fetch(`${{BASE_URL}}{path}`, {{\n"
                f"    method: '{method.upper()}',\n"
                f"    headers: {{ 'Content-Type': 'application/json' }},\n"
                f"    body: JSON.stringify(data),\n"
                f"  }});\n"
                f"  if (!r.ok) throw new Error(`{fn_name} failed: ${{r.status}}`);\n"
                f"  return r.json();\n"
                f"}}\n"
            )
        else:
            fns.append(
                f"export async function {fn_name}(params = {{}}) {{\n"
                f"  const qs = new URLSearchParams(params).toString();\n"
                f"  const url = qs ? `${{BASE_URL}}{path}?${{qs}}` : `${{BASE_URL}}{path}`;\n"
                f"  const r = await fetch(url);\n"
                f"  if (!r.ok) throw new Error(`{fn_name} failed: ${{r.status}}`);\n"
                f"  return r.json();\n"
                f"}}\n"
            )

    fn_block = "\n".join(fns)
    return f"""const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

{fn_block}"""


def _frontend_state(project_title: str, features: list[str], user_flows: list[dict[str, Any]], is_study: bool) -> str:
    assets = [
        {"id": "asset-1", "type": "summary", "title": features[0] if features else project_title, "status": "ready"},
        {"id": "asset-2", "type": "quiz", "title": "Adaptive quiz set" if is_study else "Validation checklist", "status": "draft"},
        {"id": "asset-3", "type": "plan" if is_study else "dashboard", "title": "Personalized study planner" if is_study else "Personalized dashboard", "status": "live"},
        {"id": "asset-4", "type": "progress" if is_study else "activity", "title": "Progress tracking" if is_study else "Activity tracking", "status": "live"},
    ]
    review = [
        {"id": "q1", "question": "What concept needs review next?", "answer": "Spaced repetition queue" if is_study else "Highest-risk workflow"},
        {"id": "q2", "question": "What is the next recommended action?", "answer": "Review weak topics" if is_study else "Complete validation"},
    ]
    metrics = [
        {"label": "Features", "value": str(len(features)), "detail": "Generated feature modules"},
        {"label": "Flows", "value": str(max(1, len(user_flows))), "detail": "End-to-end user journeys"},
        {"label": "Tests", "value": "API", "detail": "Backend smoke coverage included"},
        {"label": "Progress", "value": "86%" if is_study else "Ready", "detail": "Demo seed data available"},
    ]
    return (
        f"export const seedAssets = {json.dumps(assets, indent=2)};\n\n"
        f"export const reviewQueue = {json.dumps(review, indent=2)};\n\n"
        f"export const dashboardMetrics = {json.dumps(metrics, indent=2)};\n"
    )


def _seed_json(
    project_title: str,
    idea: str,
    features: list[str],
    user_flows: list[dict[str, Any]],
    is_study: bool,
) -> str:
    if is_study:
        payload = {
            "project": project_title,
            "idea": idea,
            "demo_user": {"email": "avery.student@example.com", "role": "student"},
            "study_assets": [
                {
                    "id": "notes-photosynthesis",
                    "title": "Photosynthesis Lecture Notes",
                    "type": "lecture_notes",
                    "status": "parsed",
                    "weak_topics": ["Calvin cycle", "light reactions"],
                }
            ],
            "study_plan": [
                {"day": "Monday", "task": "Review flashcards for light reactions", "minutes": 25},
                {"day": "Wednesday", "task": "Take adaptive quiz on Calvin cycle", "minutes": 20},
                {"day": "Friday", "task": "Upload new lecture notes and refresh plan", "minutes": 30},
            ],
            "flashcards": [
                {"front": "What does chlorophyll absorb?", "back": "Light energy for photosynthesis", "due": "today"},
                {"front": "Where does the Calvin cycle occur?", "back": "The stroma of chloroplasts", "due": "tomorrow"},
            ],
            "quizzes": [
                {"question": "Which stage fixes carbon dioxide?", "answer": "Calvin cycle", "difficulty": "medium"}
            ],
            "progress": {"readiness": 86, "streak_days": 5, "cards_due": 12},
            "features": features,
            "user_flows": user_flows,
        }
    else:
        payload = {
            "project": project_title,
            "idea": idea,
            "demo_user": {"email": "demo@example.com", "role": "owner"},
            "records": [
                {"id": "record-1", "title": features[0] if features else project_title, "status": "ready"},
                {"id": "record-2", "title": "Dashboard sample", "status": "in_review"},
            ],
            "activity": [
                {"type": "created", "title": "Seed record created", "status": "complete"},
                {"type": "reviewed", "title": "Demo workflow verified", "status": "complete"},
            ],
            "features": features,
            "user_flows": user_flows,
        }
    return json.dumps(payload, indent=2) + "\n"


def _seed_script() -> str:
    return (
        '"""Load demo seed data into the local generated-project database."""\n\n'
        "from __future__ import annotations\n\n"
        "import json\n"
        "from pathlib import Path\n\n"
        "from backend.db import save_activity\n\n\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "SEED_PATH = ROOT / 'data' / 'seed.json'\n\n\n"
        "def main() -> None:\n"
        "    payload = json.loads(SEED_PATH.read_text(encoding='utf-8'))\n"
        "    for item in payload.get('activity', []):\n"
        "        save_activity(item)\n"
        "    for item in payload.get('study_assets', []):\n"
        "        save_activity({'type': item.get('type', 'study_asset'), 'title': item.get('title'), 'status': item.get('status', 'ready'), 'payload': item})\n"
        "    print(f\"Seeded demo data for {payload.get('project', 'generated project')}.\")\n\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )


def _css() -> str:
    return (
        ":root { color: #172026; background: #f6f8fb; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }\n"
        "* { box-sizing: border-box; }\n"
        "body { margin: 0; }\n"
        ".appShell { min-height: 100vh; padding: 32px; }\n"
        ".topbar { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 24px; align-items: start; }\n"
        ".eyebrow { margin: 0 0 8px; color: #0f766e; font-size: 12px; font-weight: 800; text-transform: uppercase; }\n"
        "h1 { margin: 0; font-size: 44px; line-height: 1.05; letter-spacing: 0; }\n"
        ".lede { max-width: 820px; color: #4b5c66; font-size: 18px; line-height: 1.6; }\n"
        ".sessionCard, .panel, .workspace { border: 1px solid #d7dee8; background: #fff; border-radius: 8px; box-shadow: 0 16px 40px rgba(27, 39, 51, 0.08); }\n"
        ".sessionCard { padding: 18px; display: grid; gap: 8px; }\n"
        ".sessionCard span, .metric span, .asset span { color: #60717d; font-size: 12px; text-transform: uppercase; font-weight: 800; }\n"
        "button { border: 0; border-radius: 8px; background: #0f766e; color: white; padding: 10px 14px; font-weight: 800; cursor: pointer; }\n"
        ".tabs { display: flex; gap: 8px; flex-wrap: wrap; margin: 28px 0; }\n"
        ".tabs button { background: #fff; color: #172026; border: 1px solid #d7dee8; }\n"
        ".tabs button.active { background: #0f766e; color: #fff; border-color: #0f766e; }\n"
        ".grid, .dashboard { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }\n"
        ".panel, .workspace { padding: 24px; }\n"
        ".panel h2 { margin-top: 0; }\n"
        "li { margin: 8px 0; line-height: 1.5; }\n"
        ".workspace textarea { width: 100%; border: 1px solid #d7dee8; border-radius: 8px; padding: 14px; font: inherit; line-height: 1.5; }\n"
        ".actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }\n"
        ".status { color: #0f766e; font-weight: 800; }\n"
        ".metric, .flow, .asset { border-top: 1px solid #eef2f6; padding: 14px 0; display: grid; gap: 4px; }\n"
        ".flow code { color: #0f766e; }\n"
        ".asset { grid-template-columns: 90px 1fr 90px; align-items: center; }\n"
        "@media (max-width: 840px) { .appShell { padding: 20px; } .topbar, .grid, .dashboard { grid-template-columns: 1fr; } h1 { font-size: 34px; } }\n"
    )


def _backend_main(
    project_title: str,
    idea: str,
    features: list[str],
    api_routes: list[str],
    is_study: bool,
    database_required: bool = True,
) -> str:
    del is_study
    if database_required:
        imports = (
            "from backend.db import list_activity, save_activity\n"
            "from backend.models import TextAssetRequest\n\n\n"
        )
    else:
        imports = "\n"
    header = (
        '"""FastAPI backend generated from planned API routes."""\n\n'
        "from fastapi import FastAPI\n\n"
        f"{imports}"
        f"app = FastAPI(title={json.dumps(project_title)})\n"
        f"PROJECT_IDEA = {json.dumps(idea)}\n"
        f"PROJECT_FEATURES = {json.dumps(features, indent=2)}\n"
        f"API_ROUTES = {json.dumps(api_routes, indent=2)}\n\n\n"
        "@app.get('/health')\n"
        "def health() -> dict[str, object]:\n"
        "    return {'status': 'ok', 'service': app.title, 'routes': API_ROUTES}\n"
    )
    return header + _dynamic_backend_routes(api_routes, database_required=database_required)


def _dynamic_backend_routes(api_routes: list[str], *, database_required: bool = True) -> str:
    implemented = {"GET /health"}
    blocks: list[str] = []
    used_names: set[str] = set()
    for raw_route in api_routes:
        method, path = _split_api_route(raw_route)
        route_key = f"{method} {path}"
        if route_key in implemented or path in {"/health"}:
            continue
        if not path.startswith("/"):
            continue
        func_name = _route_function_name(method, path)
        while func_name in used_names:
            func_name = f"{func_name}_next"
        used_names.add(func_name)
        implemented.add(route_key)
        decorator = method.lower()
        if method in {"POST", "PUT", "PATCH"}:
            if database_required:
                body = (
                    f"\n\n@app.{decorator}({path!r})\n"
                    f"def {func_name}(payload: dict[str, object]) -> dict[str, object]:\n"
                    f"    save_activity({{'type': {path!r}, 'title': str(payload.get('title', {path!r})), 'status': 'saved', 'payload': payload}})\n"
                    f"    return {{'route': {path!r}, 'method': {method!r}, 'status': 'saved', 'payload': payload}}\n"
                )
            else:
                body = (
                    f"\n\n@app.{decorator}({path!r})\n"
                    f"def {func_name}(payload: dict[str, object]) -> dict[str, object]:\n"
                    f"    return {{'route': {path!r}, 'method': {method!r}, 'status': 'ok', 'payload': payload}}\n"
                )
        elif method == "DELETE":
            if database_required:
                body = (
                    f"\n\n@app.delete({path!r})\n"
                    f"def {func_name}() -> dict[str, object]:\n"
                    f"    save_activity({{'type': {path!r}, 'title': 'deleted record', 'status': 'deleted'}})\n"
                    f"    return {{'route': {path!r}, 'method': 'DELETE', 'status': 'deleted'}}\n"
                )
            else:
                body = (
                    f"\n\n@app.delete({path!r})\n"
                    f"def {func_name}() -> dict[str, object]:\n"
                    f"    return {{'route': {path!r}, 'method': 'DELETE', 'status': 'deleted'}}\n"
                )
        else:
            if database_required:
                body = (
                    f"\n\n@app.{decorator}({path!r})\n"
                    f"def {func_name}() -> dict[str, object]:\n"
                    f"    return {{'route': {path!r}, 'method': {method!r}, 'items': list_activity(), 'features': PROJECT_FEATURES[:4]}}\n"
                )
            else:
                body = (
                    f"\n\n@app.{decorator}({path!r})\n"
                    f"def {func_name}() -> dict[str, object]:\n"
                    f"    return {{'route': {path!r}, 'method': {method!r}, 'features': PROJECT_FEATURES[:4]}}\n"
                )
        blocks.append(body)
    return "".join(blocks)


def _split_api_route(route: str) -> tuple[str, str]:
    parts = str(route).strip().split(maxsplit=1)
    if len(parts) == 2 and parts[0].upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return parts[0].upper(), parts[1].strip()
    path = parts[0] if parts else "/api/items"
    return "GET", path


def _route_function_name(method: str, path: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", f"{method.lower()}_{path.lower()}").strip("_")
    return normalized or "generated_route"


def _backend_models(project_title: str, features: list[str]) -> str:
    return (
        '"""Request and response schemas for the generated project."""\n\n'
        "from pydantic import BaseModel, Field\n\n\n"
        "class LoginRequest(BaseModel):\n"
        "    email: str = 'user@example.com'\n"
        "    role: str = 'owner'\n\n\n"
        "class TextAssetRequest(BaseModel):\n"
        "    title: str = Field(min_length=1)\n"
        "    content: str = Field(min_length=1)\n"
        "    route: str | None = None\n\n\n"
        "class QuizRequest(BaseModel):\n"
        "    source_id: str | None = None\n"
        "    content: str = Field(min_length=1)\n"
        "    difficulty: str = 'adaptive'\n\n\n"
        f"PROJECT_NAME = {json.dumps(project_title)}\n"
        f"FEATURES = {json.dumps(features, indent=2)}\n"
    )


def _backend_services(project_title: str, idea: str, features: list[str], is_study: bool) -> str:
    return (
        '"""Business logic for the generated full-stack project."""\n\n'
        "from __future__ import annotations\n\n"
        "from hashlib import sha1\n"
        "from typing import Any\n\n\n"
        f"PROJECT_TITLE = {json.dumps(project_title)}\n"
        f"PROJECT_IDEA = {json.dumps(idea)}\n"
        f"FEATURES = {json.dumps(features, indent=2)}\n"
        f"IS_STUDY_PROJECT = {json.dumps(is_study)}\n\n\n"
        "def _asset_id(value: str) -> str:\n"
        "    return sha1(value.encode('utf-8')).hexdigest()[:12]\n\n\n"
        "def parse_uploaded_notes(title: str, content: str) -> dict[str, Any]:\n"
        "    words = [word.strip('.,:;!?').lower() for word in content.split() if len(word.strip('.,:;!?')) > 4]\n"
        "    key_terms = sorted(dict.fromkeys(words))[:8]\n"
        "    return {\n"
        "        'id': _asset_id(title + content),\n"
        "        'title': title,\n"
        "        'kind': 'lecture_notes' if IS_STUDY_PROJECT else 'source_document',\n"
        "        'summary': summarize_text(title, content)['summary'],\n"
        "        'key_terms': key_terms,\n"
        "        'next_actions': [\n"
        "            'Generate summary',\n"
        "            'Create quiz questions',\n"
        "            'Schedule review tasks',\n"
        "        ],\n"
        "    }\n\n\n"
        "def summarize_text(title: str, content: str) -> dict[str, Any]:\n"
        "    sentences = [part.strip() for part in content.replace('\\n', ' ').split('.') if part.strip()]\n"
        "    summary = '. '.join(sentences[:2]) or content[:240]\n"
        "    return {'title': title, 'summary': summary, 'source_length': len(content)}\n\n\n"
        "def generate_quiz(content: str, *, study_mode: bool) -> dict[str, Any]:\n"
        "    theme = 'spaced repetition' if study_mode else 'project workflow'\n"
        "    questions = [\n"
        "        {'id': 'q1', 'question': f'What is the key idea behind {theme}?', 'answer': 'Review important material at increasing intervals.'},\n"
        "        {'id': 'q2', 'question': 'Which area should the user review next?', 'answer': (content[:80] or PROJECT_TITLE)},\n"
        "    ]\n"
        "    flashcards = [\n"
        "        {'front': 'Core concept', 'back': questions[0]['answer'], 'due': 'today'},\n"
        "        {'front': 'Next action', 'back': questions[1]['answer'], 'due': 'tomorrow'},\n"
        "    ]\n"
        "    return {'questions': questions, 'flashcards': flashcards, 'study_mode': study_mode}\n\n\n"
        "def build_dashboard(idea: str, features: list[str], activity: list[dict[str, Any]]) -> dict[str, Any]:\n"
        "    return {\n"
        "        'idea': idea,\n"
        "        'feature_count': len(features),\n"
        "        'activity_count': len(activity),\n"
        "        'readiness': 86 if activity else 72,\n"
        "        'weak_topics': ['retrieval practice', 'review cadence'] if IS_STUDY_PROJECT else ['validation', 'handoff'],\n"
        "        'next_actions': features[:4],\n"
        "    }\n"
    )


def _backend_db(slug: str) -> str:
    return (
        '"""SQLite adapter with a Postgres-ready boundary for generated project state."""\n\n'
        "from __future__ import annotations\n\n"
        "import json\n"
        "import sqlite3\n"
        "from pathlib import Path\n"
        "from typing import Any\n\n\n"
        "DB_PATH = Path(__file__).resolve().parent / 'data' / 'project.db'\n\n\n"
        "def _connection() -> sqlite3.Connection:\n"
        "    DB_PATH.parent.mkdir(parents=True, exist_ok=True)\n"
        "    conn = sqlite3.connect(DB_PATH)\n"
        "    conn.row_factory = sqlite3.Row\n"
        "    conn.execute(\n"
        "        'create table if not exists activity ('\n"
        "        'id integer primary key autoincrement, type text not null, title text, status text, payload text)'\n"
        "    )\n"
        "    return conn\n\n\n"
        "def save_activity(payload: dict[str, Any]) -> dict[str, Any]:\n"
        "    with _connection() as conn:\n"
        "        cursor = conn.execute(\n"
        "            'insert into activity (type, title, status, payload) values (?, ?, ?, ?)',\n"
        "            (payload.get('type', 'event'), payload.get('title'), payload.get('status', 'new'), json.dumps(payload)),\n"
        "        )\n"
        "        conn.commit()\n"
        "    return {'id': cursor.lastrowid, **payload}\n\n\n"
        "def list_activity() -> list[dict[str, Any]]:\n"
        "    with _connection() as conn:\n"
        "        rows = conn.execute('select id, type, title, status, payload from activity order by id desc').fetchall()\n"
        "    return [{**json.loads(row['payload']), 'id': row['id']} for row in rows]\n\n\n"
        f"PROJECT_SCHEMA_PREFIX = {json.dumps(slug.replace('-', '_'))}\n"
    )


def _backend_tests(project_title: str, api_routes: list[str]) -> str:
    route_checks = []
    for raw_route in api_routes[:4]:
        method, path = _split_api_route(raw_route)
        if path == "/health":
            continue
        if method == "GET":
            route_checks.append(
                f"\n\n"
                f"def test_get_{_route_function_name(method, path)}():\n"
                f"    response = client.get({path!r})\n"
                f"    assert response.status_code == 200\n"
                f"    assert response.json()['route'] == {path!r}\n"
            )
        elif method == "POST":
            route_checks.append(
                f"\n\n"
                f"def test_post_{_route_function_name(method, path)}():\n"
                f"    response = client.post({path!r}, json={{'title': 'sample'}})\n"
                f"    assert response.status_code == 200\n"
                f"    assert response.json()['route'] == {path!r}\n"
            )
    return (
        "from fastapi.testclient import TestClient\n\n"
        "from backend.main import app\n\n\n"
        "client = TestClient(app)\n\n\n"
        "def test_health_reports_service():\n"
        "    response = client.get('/health')\n"
        "    assert response.status_code == 200\n"
        f"    assert response.json()['service'] == {json.dumps(project_title)}\n"
        + "".join(route_checks)
    )


def _project_plan(project_title: str, idea: str, requirements: dict[str, Any], features: list[str], advanced_features: list[str]) -> str:
    profile = depth_profile(str(requirements.get("project_depth") or "Advanced Project"))
    return (
        f"# {project_title} Project Plan\n\n"
        f"## Product Description\n\n{idea}\n\n"
        f"## Depth\n\n{profile['name']} - minimum features: {profile['minimum_features']}.\n\n"
        "## Personas\n\n"
        + _markdown_items(_string_list(requirements.get("user_personas")) or ["Primary user"])
        + "\n## Core Features\n\n"
        + _markdown_items(features)
        + "\n## Advanced Features\n\n"
        + _markdown_items(advanced_features)
        + "\n## Success Criteria\n\n"
        + _markdown_items(_string_list(requirements.get("success_criteria")))
    )


def _architecture(project_title: str, idea: str, stack: str, requirements: dict[str, Any], plan: dict[str, Any], warnings: list[str]) -> str:
    return (
        f"# {project_title} Architecture\n\n"
        f"Original idea: {idea}\n\n"
        "## Stack\n\n"
        f"{stack}\n\n"
        "## Frontend Architecture\n\n"
        "- React application with authenticated workspace, generation flow, review queue, and dashboard views.\n"
        "- `src/lib/api.js` isolates backend calls from the UI.\n"
        "- `src/state/projectState.js` seeds domain-specific review, dashboard, and asset state.\n\n"
        "## Backend Architecture\n\n"
        "- FastAPI app in `backend/main.py` exposes auth, upload, generation, review, dashboard, and health routes.\n"
        "- `backend/services.py` owns domain logic and can be replaced with live model/provider calls.\n"
        "- `backend/db.py` stores activity locally and marks the persistence boundary for Postgres/Supabase.\n\n"
        "## Data Model\n\n"
        + _markdown_items(_string_list(requirements.get("data_entities")))
        + "\n## API Design\n\n"
        + _markdown_items(_string_list(requirements.get("api_routes")))
        + "\n## Auth And Authorization\n\n"
        "- Development token route is included for local flow testing.\n"
        "- Production deployment should replace the dev token with Supabase Auth, Clerk, Auth.js, or the selected auth provider.\n"
        "- Service-role keys and provider secrets must remain backend-only.\n\n"
        "## Implementation Notes\n\n"
        + _markdown_items(_string_list(plan.get("implementation_steps")) or ["Generate frontend, backend, database, docs, tests, and deployment files."])
        + _warning_section(warnings)
    )


def _api_spec(project_title: str, api_routes: list[str]) -> str:
    return (
        f"# {project_title} API Spec\n\n"
        + "\n".join(f"- `{route}` - generated route contract for the project workflow." for route in api_routes)
        + "\n\nAll request handlers return JSON and avoid exposing secrets to the browser.\n"
    )


def _database_schema(slug: str, is_study: bool) -> str:
    prefix = re.sub(r"[^a-z0-9_]", "_", slug.replace("-", "_"))
    asset_name = "study_assets" if is_study else "project_assets"
    study_tables = ""
    if is_study:
        study_tables = (
            f"\ncreate table if not exists {prefix}_study_plans (\n"
            "  id uuid primary key default gen_random_uuid(),\n"
            f"  user_id uuid references {prefix}_users(id) on delete cascade,\n"
            "  week_start date not null default current_date,\n"
            "  goals text[] not null default '{}',\n"
            "  schedule jsonb not null default '[]'::jsonb,\n"
            "  created_at timestamptz not null default now()\n"
            ");\n\n"
            f"create table if not exists {prefix}_progress_events (\n"
            "  id uuid primary key default gen_random_uuid(),\n"
            f"  user_id uuid references {prefix}_users(id) on delete cascade,\n"
            f"  asset_id uuid references {prefix}_{asset_name}(id) on delete set null,\n"
            "  event_type text not null,\n"
            "  score integer,\n"
            "  minutes integer default 0,\n"
            "  metadata jsonb not null default '{}'::jsonb,\n"
            "  created_at timestamptz not null default now()\n"
            ");\n\n"
            f"create index if not exists {prefix}_progress_user_idx on {prefix}_progress_events(user_id, created_at desc);\n"
        )
    return (
        f"-- Postgres/Supabase schema for {slug}\n"
        "create extension if not exists pgcrypto;\n\n"
        f"create table if not exists {prefix}_users (\n"
        "  id uuid primary key default gen_random_uuid(),\n"
        "  email text unique not null,\n"
        "  role text not null default 'owner',\n"
        "  created_at timestamptz not null default now()\n"
        ");\n\n"
        f"create table if not exists {prefix}_{asset_name} (\n"
        "  id uuid primary key default gen_random_uuid(),\n"
        f"  user_id uuid references {prefix}_users(id) on delete cascade,\n"
        "  title text not null,\n"
        "  source_text text,\n"
        "  parsed_summary text,\n"
        "  metadata jsonb not null default '{}'::jsonb,\n"
        "  status text not null default 'ready',\n"
        "  created_at timestamptz not null default now()\n"
        ");\n\n"
        f"create table if not exists {prefix}_generated_items (\n"
        "  id uuid primary key default gen_random_uuid(),\n"
        f"  asset_id uuid references {prefix}_{asset_name}(id) on delete cascade,\n"
        "  item_type text not null,\n"
        "  prompt text,\n"
        "  answer text,\n"
        "  due_at timestamptz,\n"
        "  confidence integer default 0,\n"
        "  created_at timestamptz not null default now()\n"
        ");\n\n"
        f"create table if not exists {prefix}_activity_logs (\n"
        "  id uuid primary key default gen_random_uuid(),\n"
        "  user_id uuid,\n"
        "  event_type text not null,\n"
        "  payload jsonb not null default '{}'::jsonb,\n"
        "  created_at timestamptz not null default now()\n"
        ");\n\n"
        f"{study_tables}"
        f"create index if not exists {prefix}_{asset_name}_user_idx on {prefix}_{asset_name}(user_id, created_at desc);\n"
        f"create index if not exists {prefix}_generated_items_due_idx on {prefix}_generated_items(due_at, confidence);\n"
    )


def _testing_strategy(project_title: str, depth: str) -> str:
    return (
        f"# {project_title} Testing Strategy\n\n"
        f"Depth target: {depth}.\n\n"
        "- Unit test service functions for parsing, generation, and dashboard metrics.\n"
        "- API integration test health, upload, quiz, and dashboard routes.\n"
        "- Frontend build check with `npm run build`.\n"
        "- Add journey tests for sign-in, upload, generation, review, and dashboard once browser automation is configured.\n"
        "- Keep provider integrations behind adapters so missing credentials fail with actionable errors.\n"
    )


def _deploy_doc(project_title: str) -> str:
    from agent.project_depth import deploy_readme_section

    return deploy_readme_section(project_title=project_title, repo_url=None)


def _agent_log(project_title: str, requirements: dict[str, Any], plan: dict[str, Any], warnings: list[str]) -> str:
    agent_assignments = _string_list(plan.get("agent_assignments")) or [
        "Product Strategist Agent expanded requirements.",
        "Research/RAG Agent collected source context.",
        "System Architect Agent planned architecture.",
        "Data/API Agent designed API and data model.",
        "Frontend Agent generated UI flows.",
        "Backend Agent generated services and routes.",
        "QA Agent generated validation strategy.",
        "Documentation Agent generated docs.",
        "GitHub Agent exports repository files.",
    ]
    return (
        f"# {project_title} Agent Log\n\n"
        f"Project depth: {requirements.get('project_depth', 'Advanced Project')}\n\n"
        + _markdown_items(agent_assignments)
        + _warning_section(warnings)
    )


def _build_log(project_title: str, stack: str, depth: str, features: list[str], warnings: list[str]) -> str:
    return (
        f"# {project_title} Build Log\n\n"
        "- Configured LLM and LangGraph orchestration attempted full project planning before file generation.\n"
        "- Product, research, architecture, data/API, frontend, backend, QA, docs, GitHub, and logger agents contributed to the plan.\n"
        "- Generation mode: explicit **degraded** path using project-specific local scaffolds when live LLM output was unavailable.\n"
        f"- Project depth: {depth}.\n"
        f"- Selected stack: {stack}.\n"
        f"- Generated {len(features)} feature-oriented implementation targets.\n"
        "- Generated source files, tests, architecture docs, database schema, setup, and deployment instructions.\n"
        + _warning_section(warnings)
    )


def _limitations(project_title: str) -> str:
    return (
        f"# {project_title} Known Limitations\n\n"
        "- Local development auth uses a development token route and should be replaced before production.\n"
        "- AI provider calls are isolated behind service functions and need real credentials for live generation.\n"
        "- SQLite is included for local persistence; run the Postgres schema for production.\n"
        "- Browser journey tests should be added once the deployment target is selected.\n\n"
        "## Future Improvements\n\n"
        "- Add background jobs for long-running generation tasks.\n"
        "- Add role-specific authorization policies.\n"
        "- Add richer analytics and user notifications.\n"
    )


def _walkthrough(
    project_title: str,
    idea: str,
    features: list[str],
    user_flows: list[dict[str, Any]],
    api_routes: list[str],
    is_study: bool,
) -> str:
    flows = user_flows or [
        {"step": "1", "screen": "Workspace", "action": "Sign in and open the workspace", "api": "POST /api/auth/login"},
        {"step": "2", "screen": "Generate", "action": "Create project assets", "api": "POST /api/uploads"},
        {"step": "3", "screen": "Dashboard", "action": "Review generated outputs", "api": "GET /api/dashboard"},
    ]
    study_note = (
        "\nThis walkthrough demonstrates StudyPilot's full study loop: dashboard, planner, upload, flashcards, quizzes, and progress tracking.\n"
        if is_study
        else ""
    )
    return (
        f"# {project_title} Walkthrough\n\n"
        f"Project idea: {idea}\n\n"
        "## Product Features To Show\n\n"
        + _markdown_items(features[:8])
        + study_note
        + "\n## Click Path\n\n"
        + "\n".join(
            f"{index + 1}. **{step.get('screen', 'Screen')}** - {step.get('action', 'Action')} (`{step.get('api', 'UI')}`)"
            for index, step in enumerate(flows)
            if isinstance(step, dict)
        )
        + "\n\n## API Evidence\n\n"
        + _markdown_items(api_routes)
    )


def _demo_script(
    project_title: str,
    idea: str,
    features: list[str],
    user_flows: list[dict[str, Any]],
    api_routes: list[str],
    is_study: bool,
) -> str:
    flows = [flow for flow in user_flows if isinstance(flow, dict)] or [
        {"screen": "Workspace", "action": "Sign in and run the primary workflow", "api": "POST /api/auth/login"},
        {"screen": "Dashboard", "action": "Review results", "api": "GET /api/dashboard"},
    ]
    focus_line = (
        "The demo must show the dashboard, study planner, file upload, generated flashcards, quiz flow, and progress tracking."
        if is_study
        else "The demo must show the dashboard, authenticated workflow, sample data, API-backed result, and deployment-ready handoff."
    )
    return (
        f"# {project_title} Demo Video Script\n\n"
        f"Product idea: {idea}\n\n"
        f"{focus_line}\n\n"
        "## 0:00 - Hook\n\n"
        f"\"{project_title} helps its target users complete this workflow: {idea}\"\n\n"
        "## 0:20 - Sign In And Dashboard\n\n"
        "Open the app, sign in with the demo user from `data/seed.json`, and point out the key readiness metrics.\n\n"
        "## 0:45 - Core Product Flow\n\n"
        + _flow_items(flows)
        + "\n## 1:45 - Technical Proof\n\n"
        "Show `src/App.jsx`, `backend/main.py`, `docs/DATABASE_SCHEMA.sql`, `data/seed.json`, and the tests. Confirm that API calls in the UI map to backend routes:\n\n"
        + _markdown_items(api_routes)
        + "\n## 2:30 - Hackathon Close\n\n"
        "Open `docs/HACKATHON_SUBMISSION.md`, summarize the differentiator, and point judges to setup, deployment, API docs, and this demo folder.\n"
    )


def _storyboard(
    project_title: str,
    features: list[str],
    user_flows: list[dict[str, Any]],
    api_routes: list[str],
    is_study: bool,
) -> str:
    primary_feature = features[0] if features else "primary workflow"
    flow_rows = []
    for index, flow in enumerate([f for f in user_flows if isinstance(f, dict)][:5], start=1):
        flow_rows.append(
            f"| {index} | {flow.get('screen', 'Screen')} | {flow.get('action', 'Action')} | `{flow.get('api', 'UI')}` |"
        )
    if not flow_rows:
        flow_rows = [f"| 1 | Dashboard | Show {primary_feature} | `{api_routes[0] if api_routes else 'GET /api/dashboard'}` |"]
    study_row = (
        "| Study proof | Planner, flashcards, quizzes, progress | Show a complete learning loop from upload to progress | `POST /api/files/upload`, `GET /api/progress` |\n"
        if is_study
        else ""
    )
    return (
        f"# {project_title} Storyboard\n\n"
        "| Shot | Screen | Action | Technical Proof |\n"
        "| --- | --- | --- | --- |\n"
        + "\n".join(flow_rows)
        + "\n"
        + study_row
        + "| Final | Repository | README, API docs, tests, deployment guide, demo assets | `README.md`, `docs/API_SPEC.md`, `docs/DEPLOY.md` |\n"
    )


def _video_outline(project_title: str, idea: str, features: list[str], api_routes: list[str], is_study: bool) -> str:
    study_focus = (
        "\n- StudyPilot proof: upload notes, generate a study plan, review flashcards, take a quiz, and inspect progress tracking."
        if is_study
        else ""
    )
    return (
        f"# {project_title} Video Outline\n\n"
        f"## Opening\n\nIntroduce the problem: {idea}\n\n"
        "## Product Proof\n\n"
        + _markdown_items(features[:8])
        + study_focus
        + "\n## Technical Proof\n\n"
        "- Frontend app in `src/` with polished product screens.\n"
        "- Backend API in `backend/` with auth and product routes.\n"
        "- Database/schema/models in `backend/models.py`, `backend/db.py`, and `docs/DATABASE_SCHEMA.sql`.\n"
        "- Seed/sample data in `data/seed.json` and `scripts/seed_data.py`.\n"
        "- Tests and deployment instructions are included.\n\n"
        "## Route Proof\n\n"
        + _markdown_items(api_routes)
    )


def _voiceover(project_title: str, idea: str, features: list[str], is_study: bool) -> str:
    study_line = (
        "For StudyPilot, the flow goes from uploaded notes to planner, flashcards, quizzes, and progress tracking."
        if is_study
        else "The flow uses real sample data, backend routes, and a database-ready schema."
    )
    return (
        f"# {project_title} Voiceover\n\n"
        f"\"This is {project_title}, a complete full-stack hackathon project generated for: {idea}. "
        f"The app includes {', '.join(features[:4])}. {study_line} "
        "The repository is ready for judges to run locally, inspect the API, review the schema, run tests, and follow deployment instructions.\"\n"
    )


def _hackathon_submission(
    project_title: str,
    idea: str,
    stack: str,
    features: list[str],
    api_routes: list[str],
    is_study: bool,
) -> str:
    differentiator = (
        "StudyPilot turns raw course material into a connected learning loop: planner, flashcards, quizzes, progress, and next actions."
        if is_study
        else "The project packages a real product workflow with source, API, data, tests, docs, and demo assets in one repository."
    )
    return (
        f"# {project_title} Hackathon Submission\n\n"
        f"## Problem\n\n{idea}\n\n"
        f"## Solution\n\n{differentiator}\n\n"
        f"## Tech Stack\n\n{stack}\n\n"
        "## Features\n\n"
        + _markdown_items(features)
        + "\n## API And Data Proof\n\n"
        + _markdown_items(api_routes)
        + "\n## Demo Instructions\n\n"
        "1. Follow `README.md` to run the frontend and backend.\n"
        "2. Load sample data from `data/seed.json` with `python scripts/seed_data.py`.\n"
        "3. Use `demo/script.md` and `demo/storyboard.md` to record the submission video.\n"
        "4. Show tests with `pytest` and frontend build with `npm run build`.\n\n"
        "## Judging Proof\n\n"
        "- Complete frontend app, backend API, database schema/models, auth flow, seed data, tests, docs, deployment guide, and demo materials are included.\n"
        "- `.env.example` documents configuration without committing secrets.\n"
        "- Demo assets are project-specific and can be used directly for a hackathon submission.\n"
    )


def _env_example(project_title: str) -> str:
    return (
        "VITE_API_BASE_URL=http://127.0.0.1:8000\n"
        "DATABASE_URL=sqlite:///backend/data/project.db\n"
        "AUTH_SECRET=replace-me\n"
        "AI_PROVIDER_API_KEY=\n"
        "SUPABASE_URL=\n"
        "SUPABASE_ANON_KEY=\n"
        f"# Generated for: {project_title}\n"
    )


def _feature_list(requirements: dict[str, Any], required_features: list[str] | None) -> list[str]:
    features = _string_list(required_features)
    for feature in _string_list(requirements.get("core_features")):
        if feature not in features:
            features.append(feature)
    return features[:14]


def _selected_stack(plan: dict[str, Any], resolved_stack: str) -> str:
    raw_stack = plan.get("selected_stack")
    if isinstance(raw_stack, list):
        stack = [str(item).strip() for item in raw_stack if str(item).strip()]
        if stack:
            return ", ".join(stack)
    return resolved_stack or "React, FastAPI, Postgres, Pytest"


def _warning_lines(warnings: list[dict[str, str]]) -> list[str]:
    lines = []
    for warning in warnings:
        source = warning.get("source", "source")
        message = warning.get("message", "unreadable source")
        lines.append(f"{source}: {message}")
    return lines


def _warning_section(warnings: list[str]) -> str:
    if not warnings:
        return ""
    return "\n## Source Warnings\n\n" + _markdown_items(warnings)


def _markdown_items(items: list[str]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return "- Not specified yet.\n"
    return "\n".join(f"- {item}" for item in values) + "\n"


def _flow_items(flows: list[dict[str, Any]]) -> str:
    values = []
    for flow in flows:
        if not isinstance(flow, dict):
            continue
        screen = str(flow.get("screen") or "Screen").strip()
        action = str(flow.get("action") or "Action").strip()
        api = str(flow.get("api") or "UI").strip()
        values.append(f"- {screen}: {action} (`{api}`)")
    if not values:
        return "- Open the dashboard and complete the primary product workflow (`GET /api/dashboard`).\n"
    return "\n".join(values) + "\n"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _looks_like_study_project(idea: str, features: list[str]) -> bool:
    corpus = " ".join([idea, *features]).lower()
    return any(word in corpus for word in ("study", "lecture", "quiz", "flashcard", "spaced repetition", "exam"))


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "generated-project"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _kind_from_path(path: str) -> str:
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "md": "markdown",
        "py": "python",
        "jsx": "javascript",
        "js": "javascript",
        "css": "css",
        "json": "json",
        "sql": "sql",
        "html": "html",
        "txt": "text",
    }.get(suffix, "text")


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
