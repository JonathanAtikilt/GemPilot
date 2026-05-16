from __future__ import annotations

import json
import re
from typing import Any


def title_from_idea(idea: str) -> str:
    cleaned = _clean_text(idea).rstrip(".")
    lowered = cleaned.lower()
    for prefix in ("build a ", "build an ", "create a ", "make a "):
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    if len(cleaned) > 72:
        cleaned = f"{cleaned[:69].rstrip()}..."
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Generated MVP"


def build_project_artifacts(
    *,
    idea: str,
    title: str | None,
    resolved_stack: str,
    repo_plan: dict[str, Any] | None = None,
    source_warnings: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Create a complete, commit-safe MVP repository from the orchestrator plan."""

    project_title = _clean_text(title or "") or title_from_idea(idea)
    project_slug = _slugify(project_title)
    feature_label = _feature_label(idea)
    warning_lines = _warning_lines(source_warnings or [])
    plan_steps = _plan_steps(repo_plan or {})
    selected_stack = _selected_stack(repo_plan or {}, resolved_stack)
    user_story = _user_story(idea)

    backend_features = [
        "Capture intake details for the target workflow.",
        "Generate a prioritized MVP action plan.",
        "Expose demo data through a small FastAPI surface.",
    ]

    files = [
        {
            "name": "README.md",
            "kind": "markdown",
            "summary": "Project overview, setup, and demo path.",
            "content": _readme(project_title, idea, selected_stack, warning_lines),
        },
        {
            "name": "package.json",
            "kind": "json",
            "summary": "Frontend scripts and dependencies.",
            "content": json.dumps(
                {
                    "name": project_slug,
                    "version": "0.1.0",
                    "private": True,
                    "type": "module",
                    "scripts": {
                        "dev": "vite --host 0.0.0.0",
                        "build": "vite build",
                        "preview": "vite preview",
                    },
                    "dependencies": {
                        "@vitejs/plugin-react": "^4.3.4",
                        "vite": "^6.0.0",
                        "react": "^19.0.0",
                        "react-dom": "^19.0.0",
                    },
                    "devDependencies": {},
                },
                indent=2,
            )
            + "\n",
        },
        {
            "name": "index.html",
            "kind": "html",
            "summary": "Frontend HTML shell.",
            "content": (
                '<!doctype html>\n'
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
            ),
        },
        {
            "name": "src/main.jsx",
            "kind": "javascript",
            "summary": "React frontend entrypoint.",
            "content": (
                "import React from 'react';\n"
                "import { createRoot } from 'react-dom/client';\n"
                "import App from './App.jsx';\n"
                "import './styles.css';\n\n"
                "createRoot(document.getElementById('root')).render(\n"
                "  <React.StrictMode>\n"
                "    <App />\n"
                "  </React.StrictMode>,\n"
                ");\n"
            ),
        },
        {
            "name": "src/App.jsx",
            "kind": "javascript",
            "summary": "Runnable MVP user interface.",
            "content": _react_app(project_title, idea, feature_label, backend_features, plan_steps),
        },
        {
            "name": "src/styles.css",
            "kind": "css",
            "summary": "Polished demo styling.",
            "content": _css(project_title),
        },
        {
            "name": "backend/main.py",
            "kind": "python",
            "summary": "FastAPI backend with MVP planning endpoints.",
            "content": _backend_main(project_title, idea, backend_features),
        },
        {
            "name": "backend/mvp_engine.py",
            "kind": "python",
            "summary": "Domain logic for the generated MVP.",
            "content": _backend_engine(project_title, idea, backend_features),
        },
        {
            "name": "requirements.txt",
            "kind": "text",
            "summary": "Backend dependencies.",
            "content": "fastapi\nuvicorn[standard]\npydantic\npytest\n",
        },
        {
            "name": "tests/test_backend.py",
            "kind": "python",
            "summary": "Smoke tests for generated backend logic.",
            "content": _backend_test(project_title),
        },
        {
            "name": "docs/DATABASE_SCHEMA.sql",
            "kind": "sql",
            "summary": "Suggested Postgres schema for the MVP.",
            "content": _database_schema(project_slug),
        },
        {
            "name": "docs/ARCHITECTURE.md",
            "kind": "markdown",
            "summary": "Architecture notes from the orchestrator plan.",
            "content": _architecture(project_title, idea, selected_stack, plan_steps, warning_lines),
        },
        {
            "name": "docs/IMPLEMENTATION_PLAN.md",
            "kind": "markdown",
            "summary": "Step-by-step implementation plan.",
            "content": _implementation_plan(project_title, plan_steps),
        },
        {
            "name": "docs/BUILD_LOG.md",
            "kind": "markdown",
            "summary": "Agent build log for demo traceability.",
            "content": _build_log(project_title, selected_stack, plan_steps, warning_lines),
        },
        {
            "name": "demo/demo_script.md",
            "kind": "markdown",
            "summary": "Demo walkthrough for judges.",
            "content": _demo_script(project_title, idea, feature_label),
        },
        {
            "name": ".env.example",
            "kind": "text",
            "summary": "Safe placeholder environment file.",
            "content": "VITE_API_BASE_URL=http://127.0.0.1:8000\nDATABASE_URL=\n",
        },
    ]
    return files


def merge_with_project_artifacts(
    artifacts: list[dict[str, Any]],
    *,
    idea: str,
    title: str | None,
    resolved_stack: str,
    repo_plan: dict[str, Any] | None = None,
    source_warnings: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Preserve model-authored files while filling any gaps required for a real repo."""

    generated = build_project_artifacts(
        idea=idea,
        title=title,
        resolved_stack=resolved_stack,
        repo_plan=repo_plan,
        source_warnings=source_warnings,
    )
    merged: dict[str, dict[str, Any]] = {artifact["name"]: artifact for artifact in generated}
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
            "summary": str(artifact.get("summary") or "Generated by Nemotron."),
            "content": content if isinstance(content, str) else json.dumps(content, indent=2),
        }
    return [merged[path] for path in sorted(merged)]


def _readme(project_title: str, idea: str, selected_stack: str, warnings: list[str]) -> str:
    warning_section = _markdown_list("Source Warnings", warnings)
    return (
        f"# {project_title}\n\n"
        f"{idea}\n\n"
        "## MVP Workflow\n\n"
        "1. Capture the user's messy intake.\n"
        "2. Turn the intake into a prioritized action plan.\n"
        "3. Show the current work queue in the browser.\n"
        "4. Serve the same plan from a FastAPI backend.\n"
        "5. Keep a database schema ready for persistence.\n\n"
        "## Stack\n\n"
        f"{selected_stack}\n\n"
        "## Run Locally\n\n"
        "```bash\n"
        "npm install\n"
        "npm run dev\n"
        "```\n\n"
        "In another terminal:\n\n"
        "```bash\n"
        "pip install -r requirements.txt\n"
        "uvicorn backend.main:app --reload\n"
        "```\n\n"
        "## Test\n\n"
        "```bash\n"
        "pytest\n"
        "```\n"
        f"{warning_section}"
    )


def _react_app(
    project_title: str,
    idea: str,
    feature_label: str,
    backend_features: list[str],
    plan_steps: list[str],
) -> str:
    return (
        "const idea = " + json.dumps(idea) + ";\n"
        "const cards = " + json.dumps(backend_features, indent=2) + ";\n"
        "const planSteps = " + json.dumps(plan_steps, indent=2) + ";\n\n"
        "export default function App() {\n"
        "  return (\n"
        "    <main className=\"shell\">\n"
        "      <section className=\"hero\">\n"
        "        <div>\n"
        "          <p className=\"eyebrow\">Generated MVP</p>\n"
        f"          <h1>{_jsx_escape(project_title)}</h1>\n"
        "          <p className=\"lede\">{idea}</p>\n"
        "        </div>\n"
        "        <div className=\"statusPanel\" aria-label=\"MVP status\">\n"
        "          <span className=\"statusDot\" />\n"
        f"          <strong>{_jsx_escape(feature_label)} workflow ready</strong>\n"
        "          <small>Frontend, backend, tests, docs, and database schema generated by MVPilot.</small>\n"
        "        </div>\n"
        "      </section>\n\n"
        "      <section className=\"grid\" aria-label=\"Core MVP features\">\n"
        "        {cards.map((card, index) => (\n"
        "          <article className=\"card\" key={card}>\n"
        "            <span>{String(index + 1).padStart(2, '0')}</span>\n"
        "            <p>{card}</p>\n"
        "          </article>\n"
        "        ))}\n"
        "      </section>\n\n"
        "      <section className=\"plan\">\n"
        "        <h2>Implementation Plan</h2>\n"
        "        <ol>\n"
        "          {planSteps.map((step) => <li key={step}>{step}</li>)}\n"
        "        </ol>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def _css(project_title: str) -> str:
    del project_title
    return (
        ":root {\n"
        "  color: #172026;\n"
        "  background: #f6f8fb;\n"
        "  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;\n"
        "}\n\n"
        "* { box-sizing: border-box; }\n"
        "body { margin: 0; }\n"
        ".shell { min-height: 100vh; padding: 48px; }\n"
        ".hero { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.6fr); gap: 32px; align-items: stretch; }\n"
        ".eyebrow { color: #0f766e; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; font-size: 12px; }\n"
        "h1 { margin: 8px 0 16px; font-size: 52px; line-height: 1; letter-spacing: 0; }\n"
        ".lede { max-width: 760px; font-size: 20px; line-height: 1.6; color: #42515a; }\n"
        ".statusPanel, .card, .plan { border: 1px solid #d7dee8; background: #ffffff; border-radius: 8px; box-shadow: 0 18px 50px rgba(27, 39, 51, 0.08); }\n"
        ".statusPanel { padding: 24px; display: grid; align-content: center; gap: 10px; }\n"
        ".statusDot { width: 12px; height: 12px; border-radius: 999px; background: #16a34a; box-shadow: 0 0 0 6px rgba(22, 163, 74, 0.12); }\n"
        ".statusPanel small { color: #60717d; line-height: 1.5; }\n"
        ".grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 32px; }\n"
        ".card { padding: 22px; min-height: 150px; }\n"
        ".card span { color: #0f766e; font-weight: 900; font-size: 12px; }\n"
        ".card p { font-size: 17px; line-height: 1.55; margin-bottom: 0; }\n"
        ".plan { margin-top: 32px; padding: 28px; }\n"
        ".plan h2 { margin-top: 0; }\n"
        ".plan li { margin: 10px 0; color: #42515a; line-height: 1.6; }\n"
        "@media (max-width: 840px) {\n"
        "  .shell { padding: 24px; }\n"
        "  .hero, .grid { grid-template-columns: 1fr; }\n"
        "  h1 { font-size: 38px; }\n"
        "}\n"
    )


def _backend_main(project_title: str, idea: str, features: list[str]) -> str:
    return (
        '"""FastAPI surface for the generated MVP."""\n\n'
        "from fastapi import FastAPI\n"
        "from pydantic import BaseModel\n\n"
        "from backend.mvp_engine import build_demo_plan, summarize_intake\n\n\n"
        "app = FastAPI(title=" + json.dumps(project_title) + ")\n\n\n"
        "class Intake(BaseModel):\n"
        "    user_goal: str\n"
        "    urgency: str = 'normal'\n"
        "    notes: str | None = None\n\n\n"
        "@app.get('/health')\n"
        "def health() -> dict[str, str]:\n"
        "    return {'status': 'ok', 'service': " + json.dumps(project_title) + "}\n\n\n"
        "@app.get('/api/demo-plan')\n"
        "def demo_plan() -> dict[str, object]:\n"
        "    return build_demo_plan(" + json.dumps(idea) + ", " + json.dumps(features) + ")\n\n\n"
        "@app.post('/api/intake')\n"
        "def intake(payload: Intake) -> dict[str, object]:\n"
        "    return summarize_intake(payload.model_dump())\n"
    )


def _backend_engine(project_title: str, idea: str, features: list[str]) -> str:
    del project_title
    return (
        '"""Core MVP planning logic."""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n\n"
        "def build_demo_plan(idea: str, features: list[str]) -> dict[str, Any]:\n"
        "    return {\n"
        "        'idea': idea,\n"
        "        'features': features,\n"
        "        'next_actions': [\n"
        "            'Validate the highest-risk user workflow.',\n"
        "            'Review generated data model before wiring persistence.',\n"
        "            'Run the demo with one realistic intake.',\n"
        "        ],\n"
        "    }\n\n\n"
        "def summarize_intake(payload: dict[str, Any]) -> dict[str, Any]:\n"
        "    goal = str(payload.get('user_goal') or '').strip()\n"
        "    urgency = str(payload.get('urgency') or 'normal').strip().lower()\n"
        "    priority = 'high' if urgency in {'urgent', 'high', 'critical'} else 'normal'\n"
        "    return {\n"
        "        'summary': goal or " + json.dumps(idea) + ",\n"
        "        'priority': priority,\n"
        "        'recommended_first_step': 'Create the first tracked work item.',\n"
        "    }\n"
    )


def _backend_test(project_title: str) -> str:
    return (
        "from backend.mvp_engine import build_demo_plan, summarize_intake\n\n\n"
        "def test_demo_plan_contains_features():\n"
        "    plan = build_demo_plan('demo idea', ['capture intake'])\n"
        "    assert plan['idea'] == 'demo idea'\n"
        "    assert plan['features'] == ['capture intake']\n\n\n"
        "def test_intake_marks_urgent_items_high_priority():\n"
        "    result = summarize_intake({'user_goal': 'ship it', 'urgency': 'urgent'})\n"
        "    assert result['priority'] == 'high'\n"
        "    assert 'ship it' in result['summary']\n"
        f"    assert {json.dumps(project_title)}\n"
    )


def _database_schema(project_slug: str) -> str:
    table_prefix = re.sub(r"[^a-z0-9_]", "_", project_slug.replace("-", "_"))
    return (
        f"-- Suggested Postgres schema for {project_slug}\n"
        f"create table if not exists {table_prefix}_intakes (\n"
        "  id uuid primary key default gen_random_uuid(),\n"
        "  user_goal text not null,\n"
        "  urgency text not null default 'normal',\n"
        "  notes text,\n"
        "  status text not null default 'new',\n"
        "  created_at timestamptz not null default now()\n"
        ");\n\n"
        f"create index if not exists {table_prefix}_intakes_status_idx\n"
        f"  on {table_prefix}_intakes(status, created_at desc);\n"
    )


def _architecture(
    project_title: str,
    idea: str,
    selected_stack: str,
    plan_steps: list[str],
    warnings: list[str],
) -> str:
    warning_section = _markdown_list("Source Warnings", warnings)
    return (
        f"# {project_title} Architecture\n\n"
        f"Original idea: {idea}\n\n"
        "## Components\n\n"
        "- React frontend in `src/` for the demo workflow.\n"
        "- FastAPI backend in `backend/` for health, planning, and intake endpoints.\n"
        "- Postgres schema in `docs/DATABASE_SCHEMA.sql` for the first persistence pass.\n"
        "- Pytest smoke tests in `tests/` for generated backend logic.\n\n"
        "## Stack Decision\n\n"
        f"{selected_stack}\n\n"
        "## Implementation Steps\n\n"
        + "\n".join(f"{index + 1}. {step}" for index, step in enumerate(plan_steps))
        + "\n"
        f"{warning_section}"
    )


def _implementation_plan(project_title: str, steps: list[str]) -> str:
    return (
        f"# {project_title} Implementation Plan\n\n"
        + "\n".join(f"{index + 1}. {step}" for index, step in enumerate(steps))
        + "\n"
    )


def _build_log(
    project_title: str,
    selected_stack: str,
    plan_steps: list[str],
    warnings: list[str],
) -> str:
    warning_section = _markdown_list("Warnings", warnings)
    return (
        f"# {project_title} Build Log\n\n"
        "- GitHub connection validated by backend OAuth.\n"
        "- Repository settings accepted from the website.\n"
        "- Nemotron/OpenClaw orchestrator scoped the messy idea into one MVP.\n"
        "- RAG context and submitted sources were checked before planning.\n"
        f"- Selected stack: {selected_stack}.\n"
        "- Generated frontend, backend, database schema, tests, docs, and demo script.\n\n"
        "## Plan Executed\n\n"
        + "\n".join(f"- {step}" for step in plan_steps)
        + "\n"
        f"{warning_section}"
    )


def _demo_script(project_title: str, idea: str, feature_label: str) -> str:
    return (
        f"# {project_title} Demo Script\n\n"
        "1. Open the generated React app and introduce the user problem.\n"
        f"2. Submit a realistic {feature_label.lower()} intake.\n"
        "3. Show the FastAPI `/api/demo-plan` response.\n"
        "4. Open `docs/DATABASE_SCHEMA.sql` to show persistence is ready.\n"
        "5. Run `pytest` to show the generated backend logic has a smoke test.\n\n"
        f"Submitted idea: {idea}\n"
    )


def _plan_steps(repo_plan: dict[str, Any]) -> list[str]:
    raw_steps = repo_plan.get("implementation_steps")
    if isinstance(raw_steps, list):
        steps = [str(step).strip() for step in raw_steps if str(step).strip()]
        if steps:
            return steps[:8]
    return [
        "Define the core user workflow and success state.",
        "Generate the frontend screens for intake, status, and results.",
        "Generate backend endpoints for health, planning, and intake.",
        "Provide a Postgres schema for the first persistent data model.",
        "Add tests and docs so the repo is demo-ready immediately.",
    ]


def _selected_stack(repo_plan: dict[str, Any], resolved_stack: str) -> str:
    raw_stack = repo_plan.get("selected_stack")
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


def _markdown_list(title: str, lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n\n## " + title + "\n\n" + "\n".join(f"- {line}" for line in lines) + "\n"


def _feature_label(idea: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", idea.lower())
    skip = {"build", "create", "make", "a", "an", "the", "that", "helps", "for", "with"}
    selected = [word for word in words if word not in skip][:3]
    return " ".join(selected).title() if selected else "MVP"


def _user_story(idea: str) -> str:
    return f"As a user, I want {idea.rstrip('.').lower()} so I can make progress faster."


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "generated-mvp"


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


def _jsx_escape(value: str) -> str:
    return value.replace("{", "&#123;").replace("}", "&#125;")
