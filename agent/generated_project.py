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
    domain = _domain_context(project_title, idea)

    backend_features = [
        f"Capture {domain['record_label'].lower()} requests with priority, owner, and due date.",
        f"Turn each intake into a {domain['workflow_label'].lower()} workflow with next actions.",
        f"Expose {domain['metric_label'].lower()}, queue, and intake summaries through FastAPI.",
    ]

    files = [
        {
            "name": "README.md",
            "kind": "markdown",
            "summary": "Project overview, setup, and demo path.",
            "content": _readme(project_title, idea, selected_stack, warning_lines, domain, user_story),
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
                        "react": "^19.2.6",
                        "react-dom": "^19.2.6",
                    },
                    "devDependencies": {
                        "@vitejs/plugin-react": "^6.0.1",
                        "vite": "^8.0.0",
                    },
                },
                indent=2,
            )
            + "\n",
        },
        {
            "name": "vite.config.js",
            "kind": "javascript",
            "summary": "Vite React configuration.",
            "content": (
                "import { defineConfig } from 'vite';\n"
                "import react from '@vitejs/plugin-react';\n\n"
                "export default defineConfig({\n"
                "  plugins: [react()],\n"
                "});\n"
            ),
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
            "name": "src/api.js",
            "kind": "javascript",
            "summary": "Small API client for the generated FastAPI backend.",
            "content": _api_client(),
        },
        {
            "name": "src/App.jsx",
            "kind": "javascript",
            "summary": "Runnable MVP user interface.",
            "content": _react_app(project_title, idea, feature_label, backend_features, plan_steps, domain, user_story),
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
            "content": _backend_main(project_title, idea, backend_features, domain),
        },
        {
            "name": "backend/mvp_engine.py",
            "kind": "python",
            "summary": "Domain logic for the generated MVP.",
            "content": _backend_engine(project_title, idea, backend_features, domain, plan_steps),
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
            "content": _architecture(project_title, idea, selected_stack, plan_steps, warning_lines, domain),
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
            "content": _demo_script(project_title, idea, feature_label, domain),
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


def _readme(
    project_title: str,
    idea: str,
    selected_stack: str,
    warnings: list[str],
    domain: dict[str, Any],
    user_story: str,
) -> str:
    warning_section = _markdown_list("Source Warnings", warnings)
    return (
        f"# {project_title}\n\n"
        f"{idea}\n\n"
        f"{user_story}\n\n"
        "## MVP Workflow\n\n"
        f"1. Capture a {domain['record_label'].lower()} intake with owner, segment, priority, and deadline.\n"
        f"2. Convert the intake into a {domain['workflow_label'].lower()} queue item with next actions.\n"
        f"3. Show {domain['metric_label'].lower()}, active work, and blocked items in the browser.\n"
        "4. Serve the same demo data from FastAPI endpoints.\n"
        "5. Keep a database schema ready for persistence without storing secrets.\n\n"
        "## Demo Data Included\n\n"
        f"- Sample audience: {domain['audience']}.\n"
        f"- Primary record: {domain['record_label']}.\n"
        f"- Default owner: {domain['owner']}.\n"
        f"- First workflow state: {domain['workflow'][0]}.\n\n"
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
    domain: dict[str, Any],
    user_story: str,
) -> str:
    demo_data = _demo_data(project_title, idea, backend_features, domain, plan_steps)
    return (
        "import { useMemo, useState } from 'react';\n\n"
        "import { submitIntake } from './api.js';\n\n"
        "const idea = " + json.dumps(idea) + ";\n"
        "const userStory = " + json.dumps(user_story) + ";\n"
        "const cards = " + json.dumps(backend_features, indent=2) + ";\n"
        "const planSteps = " + json.dumps(plan_steps, indent=2) + ";\n\n"
        "const demo = " + json.dumps(demo_data, indent=2) + ";\n\n"
        "export default function App() {\n"
        "  const [intake, setIntake] = useState(demo.intake_template);\n"
        "  const [queue, setQueue] = useState(demo.queue);\n"
        "  const [submitState, setSubmitState] = useState({ status: 'idle', message: 'Ready to queue a new item.' });\n"
        "  const preview = useMemo(() => ({\n"
        "    summary: intake.goal || demo.intake_template.goal,\n"
        "    owner: intake.owner,\n"
        "    priority: intake.priority,\n"
        "    segment: intake.segment,\n"
        "    recommended_next_step: demo.next_actions[0],\n"
        "  }), [intake]);\n\n"
        "  function updateIntake(event) {\n"
        "    const { name, value } = event.target;\n"
        "    setIntake((current) => ({ ...current, [name]: value }));\n"
        "  }\n\n"
        "  async function queueIntake() {\n"
        "    setSubmitState({ status: 'saving', message: 'Submitting intake...' });\n"
        "    const result = await submitIntake(intake);\n"
        "    const queuedItem = {\n"
        "      id: `item-${Date.now()}`,\n"
        "      title: result.summary || intake.goal,\n"
        "      segment: result.segment || intake.segment,\n"
        "      owner: result.owner || intake.owner,\n"
        "      priority: result.priority === 'high' ? 'High' : intake.priority,\n"
        "      status: result.status || demo.workflow[0],\n"
        "      due: 'new',\n"
        "    };\n"
        "    setQueue((current) => [queuedItem, ...current]);\n"
        "    setSubmitState({\n"
        "      status: result.offline ? 'offline' : 'saved',\n"
        "      message: result.offline ? 'Queued locally. Start the FastAPI backend to persist responses.' : 'Queued through the API.',\n"
        "    });\n"
        "  }\n\n"
        "  return (\n"
        "    <main className=\"shell\">\n"
        "      <section className=\"hero\">\n"
        "        <div>\n"
        "          <p className=\"eyebrow\">Generated MVP</p>\n"
        f"          <h1>{_jsx_escape(project_title)}</h1>\n"
        "          <p className=\"lede\">{idea}</p>\n"
        "          <p className=\"story\">{userStory}</p>\n"
        "        </div>\n"
        "        <div className=\"statusPanel\" aria-label=\"MVP status\">\n"
        "          <span className=\"statusDot\" />\n"
        f"          <strong>{_jsx_escape(feature_label)} workflow ready</strong>\n"
        "          <small>{demo.audience} can review live queue state, submit a realistic intake, and inspect matching API payloads.</small>\n"
        "        </div>\n"
        "      </section>\n\n"
        "      <section className=\"metrics\" aria-label=\"Demo metrics\">\n"
        "        {demo.metrics.map((metric) => (\n"
        "          <article className=\"metric\" key={metric.label}>\n"
        "            <span>{metric.label}</span>\n"
        "            <strong>{metric.value}</strong>\n"
        "            <small>{metric.delta}</small>\n"
        "          </article>\n"
        "        ))}\n"
        "      </section>\n\n"
        "      <section className=\"grid\" aria-label=\"Core MVP features\">\n"
        "        {cards.map((card, index) => (\n"
        "          <article className=\"card\" key={card}>\n"
        "            <span>{String(index + 1).padStart(2, '0')}</span>\n"
        "            <p>{card}</p>\n"
        "          </article>\n"
        "        ))}\n"
        "      </section>\n\n"
        "      <section className=\"agentTeam\" aria-label=\"Generated agent team\">\n"
        "        <div className=\"sectionHeader\">\n"
        "          <p className=\"eyebrow\">Agent team</p>\n"
        "          <h2>Specialized subagents</h2>\n"
        "        </div>\n"
        "        <div className=\"agentGrid\">\n"
        "          {demo.agent_team.map((agent) => (\n"
        "            <article className=\"agentCard\" key={agent.name}>\n"
        "              <div><strong>{agent.name}</strong><small>{agent.role}</small></div>\n"
        "              <p>{agent.output}</p>\n"
        "              <span>{agent.status}</span>\n"
        "            </article>\n"
        "          ))}\n"
        "        </div>\n"
        "      </section>\n\n"
        "      <section className=\"workspace\" aria-label=\"MVP workspace\">\n"
        "        <form className=\"panel\" onSubmit={(event) => { event.preventDefault(); queueIntake(); }}>\n"
        "          <div className=\"sectionHeader\">\n"
        "            <p className=\"eyebrow\">Intake</p>\n"
        "            <h2>{demo.record_label}</h2>\n"
        "          </div>\n"
        "          <label>Goal<input name=\"goal\" value={intake.goal} onChange={updateIntake} /></label>\n"
        "          <label>Segment<input name=\"segment\" value={intake.segment} onChange={updateIntake} /></label>\n"
        "          <div className=\"fieldRow\">\n"
        "            <label>Priority<select name=\"priority\" value={intake.priority} onChange={updateIntake}><option>High</option><option>Normal</option><option>Low</option></select></label>\n"
        "            <label>Owner<input name=\"owner\" value={intake.owner} onChange={updateIntake} /></label>\n"
        "          </div>\n"
        "          <button type=\"submit\" disabled={submitState.status === 'saving'}>{submitState.status === 'saving' ? 'Queueing...' : 'Queue intake'}</button>\n"
        "          <small className={`submitState ${submitState.status}`}>{submitState.message}</small>\n"
        "        </form>\n\n"
        "        <section className=\"panel\">\n"
        "          <div className=\"sectionHeader\">\n"
        "            <p className=\"eyebrow\">Workflow</p>\n"
        "            <h2>{demo.workflow_label}</h2>\n"
        "          </div>\n"
        "          <div className=\"queueList\">\n"
        "            {queue.map((item) => (\n"
        "              <article className=\"queueItem\" key={item.id}>\n"
        "                <div><strong>{item.title}</strong><small>{item.segment} - {item.owner}</small></div>\n"
        "                <span className={`pill ${item.priority.toLowerCase()}`}>{item.priority}</span>\n"
        "                <small>{item.status} by {item.due}</small>\n"
        "              </article>\n"
        "            ))}\n"
        "          </div>\n"
        "        </section>\n"
        "      </section>\n\n"
        "      <section className=\"workspace lower\" aria-label=\"Plan and API preview\">\n"
        "        <section className=\"panel\">\n"
        "          <div className=\"sectionHeader\">\n"
        "            <p className=\"eyebrow\">Build plan</p>\n"
        "            <h2>Actionable next steps</h2>\n"
        "          </div>\n"
        "          <ol className=\"planList\">\n"
        "            {planSteps.map((step) => <li key={step}>{step}</li>)}\n"
        "          </ol>\n"
        "        </section>\n"
        "        <section className=\"panel apiPanel\">\n"
        "          <div className=\"sectionHeader\">\n"
        "            <p className=\"eyebrow\">API preview</p>\n"
        "            <h2>/api/intake</h2>\n"
        "          </div>\n"
        "          <pre>{JSON.stringify(preview, null, 2)}</pre>\n"
        "        </section>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def _api_client() -> str:
    return (
        "const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';\n\n"
        "export async function submitIntake(intake) {\n"
        "  const payload = {\n"
        "    user_goal: intake.goal,\n"
        "    urgency: intake.priority,\n"
        "    segment: intake.segment,\n"
        "    owner: intake.owner,\n"
        "  };\n\n"
        "  try {\n"
        "    const response = await fetch(`${API_BASE_URL}/api/intake`, {\n"
        "      method: 'POST',\n"
        "      headers: { 'Content-Type': 'application/json' },\n"
        "      body: JSON.stringify(payload),\n"
        "    });\n"
        "    if (!response.ok) {\n"
        "      throw new Error(`API returned ${response.status}`);\n"
        "    }\n"
        "    return await response.json();\n"
        "  } catch (error) {\n"
        "    return {\n"
        "      summary: intake.goal,\n"
        "      priority: intake.priority.toLowerCase(),\n"
        "      segment: intake.segment,\n"
        "      owner: intake.owner,\n"
        "      status: 'Needs review',\n"
        "      offline: true,\n"
        "      error: error instanceof Error ? error.message : 'API unavailable',\n"
        "    };\n"
        "  }\n"
        "}\n"
    )


def _css(project_title: str) -> str:
    del project_title
    return (
        ":root {\n"
        "  color: #172026;\n"
        "  background: #f4f7f9;\n"
        "  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;\n"
        "}\n\n"
        "* { box-sizing: border-box; }\n"
        "body { margin: 0; }\n"
        "button, input, select { font: inherit; }\n"
        ".shell { min-height: 100vh; padding: 40px; max-width: 1280px; margin: 0 auto; }\n"
        ".hero { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.6fr); gap: 32px; align-items: stretch; }\n"
        ".eyebrow { color: #0f766e; font-weight: 800; letter-spacing: 0; text-transform: uppercase; font-size: 12px; margin: 0; }\n"
        "h1 { margin: 8px 0 16px; font-size: 48px; line-height: 1.05; letter-spacing: 0; }\n"
        "h2 { margin: 4px 0 0; font-size: 22px; }\n"
        ".lede { max-width: 780px; font-size: 20px; line-height: 1.55; color: #42515a; }\n"
        ".story { max-width: 760px; color: #60717d; line-height: 1.6; }\n"
        ".statusPanel, .card, .metric, .panel { border: 1px solid #d7dee8; background: #ffffff; border-radius: 8px; box-shadow: 0 16px 40px rgba(27, 39, 51, 0.07); }\n"
        ".statusPanel { padding: 24px; display: grid; align-content: center; gap: 10px; }\n"
        ".statusDot { width: 12px; height: 12px; border-radius: 999px; background: #16a34a; box-shadow: 0 0 0 6px rgba(22, 163, 74, 0.12); }\n"
        ".statusPanel small { color: #60717d; line-height: 1.5; }\n"
        ".metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 32px; }\n"
        ".metric { padding: 18px; display: grid; gap: 8px; min-height: 120px; }\n"
        ".metric span, .metric small { color: #60717d; }\n"
        ".metric strong { font-size: 30px; }\n"
        ".grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 32px; }\n"
        ".card { padding: 22px; min-height: 150px; }\n"
        ".card span { color: #0f766e; font-weight: 900; font-size: 12px; }\n"
        ".card p { font-size: 17px; line-height: 1.55; margin-bottom: 0; }\n"
        ".agentTeam { margin-top: 32px; }\n"
        ".agentGrid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }\n"
        ".agentCard { border: 1px solid #d7dee8; background: #ffffff; border-radius: 8px; padding: 16px; min-height: 180px; display: grid; align-content: space-between; gap: 12px; box-shadow: 0 14px 34px rgba(27, 39, 51, 0.06); }\n"
        ".agentCard strong { display: block; font-size: 15px; }\n"
        ".agentCard small, .agentCard p { color: #60717d; line-height: 1.45; }\n"
        ".agentCard p { margin: 0; font-size: 14px; }\n"
        ".agentCard span { justify-self: start; border-radius: 999px; padding: 5px 9px; background: #ecfdf5; color: #047857; font-size: 12px; font-weight: 800; }\n"
        ".workspace { display: grid; grid-template-columns: minmax(320px, 0.8fr) minmax(0, 1.2fr); gap: 20px; margin-top: 32px; align-items: start; }\n"
        ".workspace.lower { grid-template-columns: minmax(0, 1fr) minmax(320px, 0.75fr); }\n"
        ".panel { padding: 24px; }\n"
        ".sectionHeader { margin-bottom: 18px; }\n"
        "label { display: grid; gap: 8px; color: #42515a; font-weight: 700; margin-top: 14px; }\n"
        "input, select { width: 100%; border: 1px solid #cbd5df; border-radius: 6px; padding: 11px 12px; color: #172026; background: #fbfcfe; }\n"
        ".fieldRow { display: grid; grid-template-columns: 0.7fr 1fr; gap: 12px; }\n"
        "button { margin-top: 18px; border: 0; border-radius: 6px; padding: 12px 16px; background: #0f766e; color: #ffffff; font-weight: 800; cursor: pointer; }\n"
        "button:disabled { cursor: wait; opacity: 0.7; }\n"
        ".submitState { display: block; margin-top: 10px; color: #60717d; }\n"
        ".submitState.saved { color: #047857; }\n"
        ".submitState.offline { color: #92400e; }\n"
        ".queueList { display: grid; gap: 12px; }\n"
        ".queueItem { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fbfcfe; }\n"
        ".queueItem small { color: #60717d; display: block; margin-top: 4px; }\n"
        ".pill { border-radius: 999px; padding: 5px 9px; background: #e8f5f3; color: #0f766e; font-size: 12px; font-weight: 800; align-self: start; }\n"
        ".pill.high { background: #fee2e2; color: #991b1b; }\n"
        ".pill.low { background: #eef2ff; color: #3730a3; }\n"
        ".planList { margin: 0; padding-left: 22px; }\n"
        ".planList li { margin: 10px 0; color: #42515a; line-height: 1.6; }\n"
        ".apiPanel pre { overflow: auto; margin: 0; padding: 16px; background: #162026; color: #d9f99d; border-radius: 8px; font-size: 13px; line-height: 1.5; }\n"
        "@media (max-width: 840px) {\n"
        "  .shell { padding: 24px; }\n"
        "  .hero, .grid, .metrics, .agentGrid, .workspace, .workspace.lower, .fieldRow { grid-template-columns: 1fr; }\n"
        "  h1 { font-size: 38px; }\n"
        "}\n"
    )


def _backend_main(project_title: str, idea: str, features: list[str], domain: dict[str, Any]) -> str:
    return (
        '"""FastAPI surface for the generated MVP."""\n\n'
        "from fastapi import FastAPI\n"
        "from fastapi.middleware.cors import CORSMiddleware\n"
        "from pydantic import BaseModel\n\n"
        "from backend.mvp_engine import build_demo_plan, build_demo_workspace, summarize_intake\n\n\n"
        "app = FastAPI(title=" + json.dumps(project_title) + ")\n\n\n"
        "app.add_middleware(\n"
        "    CORSMiddleware,\n"
        "    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],\n"
        "    allow_credentials=True,\n"
        "    allow_methods=['*'],\n"
        "    allow_headers=['*'],\n"
        ")\n\n\n"
        "class Intake(BaseModel):\n"
        "    user_goal: str\n"
        "    urgency: str = 'normal'\n"
        "    segment: str = " + json.dumps(domain["audience"]) + "\n"
        "    owner: str = " + json.dumps(domain["owner"]) + "\n"
        "    notes: str | None = None\n\n\n"
        "@app.get('/health')\n"
        "def health() -> dict[str, str]:\n"
        "    return {'status': 'ok', 'service': " + json.dumps(project_title) + "}\n\n\n"
        "@app.get('/api/demo-data')\n"
        "def demo_data() -> dict[str, object]:\n"
        "    return build_demo_workspace()\n\n\n"
        "@app.get('/api/demo-plan')\n"
        "def demo_plan() -> dict[str, object]:\n"
        "    return build_demo_plan(" + json.dumps(idea) + ", " + json.dumps(features) + ")\n\n\n"
        "@app.post('/api/intake')\n"
        "def intake(payload: Intake) -> dict[str, object]:\n"
        "    return summarize_intake(payload.model_dump())\n"
    )


def _backend_engine(
    project_title: str,
    idea: str,
    features: list[str],
    domain: dict[str, Any],
    plan_steps: list[str],
) -> str:
    demo_data = _demo_data(project_title, idea, features, domain, plan_steps)
    return (
        '"""Core MVP planning logic."""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n\n"
        "DEMO_WORKSPACE: dict[str, Any] = " + json.dumps(demo_data, indent=4) + "\n\n\n"
        "def build_demo_workspace() -> dict[str, Any]:\n"
        "    return DEMO_WORKSPACE\n\n\n"
        "def build_demo_plan(idea: str, features: list[str]) -> dict[str, Any]:\n"
        "    return {\n"
        "        'idea': idea,\n"
        "        'features': features,\n"
        "        'audience': DEMO_WORKSPACE['audience'],\n"
        "        'metrics': DEMO_WORKSPACE['metrics'],\n"
        "        'agent_team': DEMO_WORKSPACE['agent_team'],\n"
        "        'queue': DEMO_WORKSPACE['queue'],\n"
        "        'next_actions': DEMO_WORKSPACE['next_actions'],\n"
        "    }\n\n\n"
        "def summarize_intake(payload: dict[str, Any]) -> dict[str, Any]:\n"
        "    goal = str(payload.get('user_goal') or '').strip()\n"
        "    urgency = str(payload.get('urgency') or 'normal').strip().lower()\n"
        "    segment = str(payload.get('segment') or DEMO_WORKSPACE['audience']).strip()\n"
        "    owner = str(payload.get('owner') or DEMO_WORKSPACE['intake_template']['owner']).strip()\n"
        "    priority = 'high' if urgency in {'urgent', 'high', 'critical'} else 'normal'\n"
        "    first_action = DEMO_WORKSPACE['next_actions'][0]\n"
        "    return {\n"
        "        'summary': goal or " + json.dumps(idea) + ",\n"
        "        'priority': priority,\n"
        "        'segment': segment,\n"
        "        'owner': owner,\n"
        "        'status': DEMO_WORKSPACE['workflow'][0],\n"
        "        'recommended_first_step': first_action,\n"
        "    }\n"
    )


def _backend_test(project_title: str) -> str:
    return (
        "from backend.mvp_engine import build_demo_plan, summarize_intake\n\n\n"
        "def test_demo_plan_contains_features():\n"
        "    plan = build_demo_plan('demo idea', ['capture intake'])\n"
        "    assert plan['idea'] == 'demo idea'\n"
        "    assert plan['features'] == ['capture intake']\n"
        "    assert plan['queue']\n\n\n"
        "def test_intake_marks_urgent_items_high_priority():\n"
        "    result = summarize_intake({'user_goal': 'ship it', 'urgency': 'urgent'})\n"
        "    assert result['priority'] == 'high'\n"
        "    assert 'ship it' in result['summary']\n"
        "    assert result['recommended_first_step']\n"
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
        "  segment text not null default 'general',\n"
        "  owner_name text,\n"
        "  due_label text,\n"
        "  notes text,\n"
        "  status text not null default 'new',\n"
        "  created_at timestamptz not null default now()\n"
        ");\n\n"
        f"create index if not exists {table_prefix}_intakes_status_idx\n"
        f"  on {table_prefix}_intakes(status, created_at desc);\n"
        f"create index if not exists {table_prefix}_intakes_owner_idx\n"
        f"  on {table_prefix}_intakes(owner_name, urgency);\n"
    )


def _architecture(
    project_title: str,
    idea: str,
    selected_stack: str,
    plan_steps: list[str],
    warnings: list[str],
    domain: dict[str, Any],
) -> str:
    warning_section = _markdown_list("Source Warnings", warnings)
    return (
        f"# {project_title} Architecture\n\n"
        f"Original idea: {idea}\n\n"
        "## Components\n\n"
        "- React frontend in `src/` for the demo workflow.\n"
        f"- FastAPI backend in `backend/` for health, planning, {domain['record_label'].lower()} intake, and demo data endpoints.\n"
        "- Postgres schema in `docs/DATABASE_SCHEMA.sql` for the first persistence pass.\n"
        "- Pytest smoke tests in `tests/` for generated backend logic.\n\n"
        "## Demo Domain\n\n"
        f"- Audience: {domain['audience']}.\n"
        f"- Workflow: {', '.join(domain['workflow'])}.\n"
        f"- Metrics: {domain['metric_label']}.\n\n"
        "## Generated Subagents\n\n"
        "- Strategist Agent scopes the demo and selects the success metric.\n"
        "- Research Agent turns source context into constraints and warnings.\n"
        "- Builder Agent produces the frontend/API/database slice.\n"
        "- QA Agent checks risks, blocked work, and demo readiness.\n"
        "- Demo Agent packages the walkthrough for stakeholders.\n\n"
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


def _demo_script(project_title: str, idea: str, feature_label: str, domain: dict[str, Any]) -> str:
    return (
        f"# {project_title} Demo Script\n\n"
        "1. Open the generated React app and introduce the user problem.\n"
        f"2. Review the {domain['metric_label'].lower()} and active {feature_label.lower()} queue.\n"
        "3. Explain how each generated subagent contributes one concrete output.\n"
        f"4. Submit a realistic {domain['record_label'].lower()} intake for {domain['audience']}.\n"
        "5. Show the FastAPI `/api/demo-data`, `/api/demo-plan`, and `/api/intake` responses.\n"
        "6. Open `docs/DATABASE_SCHEMA.sql` to show persistence is ready.\n"
        "7. Run `pytest` to show the generated backend logic has a smoke test.\n\n"
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


def _domain_context(project_title: str, idea: str) -> dict[str, Any]:
    text = f"{project_title} {idea}".lower()
    if any(term in text for term in ("referral", "clinic", "patient", "care", "health")):
        return {
            "audience": "care coordinators",
            "record_label": "Referral Request",
            "workflow_label": "Care Coordination",
            "metric_label": "Referral Metrics",
            "owner": "Nina Patel",
            "workflow": ["Needs triage", "Records requested", "Specialist scheduled", "Closed loop"],
            "segments": ["Cardiology", "Imaging", "Physical therapy"],
            "sample_titles": [
                "Book cardiology follow-up after abnormal ECG",
                "Collect imaging prior authorization details",
                "Confirm post-discharge therapy availability",
            ],
        }
    if any(term in text for term in ("study", "student", "school", "course", "learn")):
        return {
            "audience": "students and advisors",
            "record_label": "Study Plan Request",
            "workflow_label": "Learning Sprint",
            "metric_label": "Progress Metrics",
            "owner": "Avery Chen",
            "workflow": ["Needs assessment", "Plan drafted", "Session booked", "Progress reviewed"],
            "segments": ["Exam prep", "Project work", "Office hours"],
            "sample_titles": [
                "Schedule biology exam review plan",
                "Break capstone project into weekly tasks",
                "Prepare office-hours question queue",
            ],
        }
    if any(term in text for term in ("sales", "crm", "lead", "pipeline", "customer")):
        return {
            "audience": "revenue teams",
            "record_label": "Lead Intake",
            "workflow_label": "Pipeline Follow-Up",
            "metric_label": "Pipeline Metrics",
            "owner": "Jordan Lee",
            "workflow": ["Needs qualification", "Discovery booked", "Proposal drafted", "Won or archived"],
            "segments": ["Enterprise", "Mid-market", "Expansion"],
            "sample_titles": [
                "Qualify inbound enterprise pilot request",
                "Prepare expansion call with active customer",
                "Draft proposal for mid-market buyer",
            ],
        }
    if any(term in text for term in ("event", "venue", "booking", "ticket")):
        return {
            "audience": "event operators",
            "record_label": "Event Request",
            "workflow_label": "Event Operations",
            "metric_label": "Booking Metrics",
            "owner": "Mara Torres",
            "workflow": ["Needs details", "Vendor hold", "Run-of-show drafted", "Ready for event"],
            "segments": ["Corporate", "Community", "Private"],
            "sample_titles": [
                "Confirm catering hold for workshop",
                "Collect AV requirements for keynote",
                "Draft run-of-show for community night",
            ],
        }
    return {
        "audience": "operators",
        "record_label": "Work Request",
        "workflow_label": "Operations Queue",
        "metric_label": "Operating Metrics",
        "owner": "Sam Rivera",
        "workflow": ["Needs review", "Ready to start", "In progress", "Done"],
        "segments": ["High value", "At risk", "New request"],
        "sample_titles": [
            "Review highest-risk user workflow",
            "Prepare stakeholder-ready pilot data",
            "Close the loop on blocked task",
        ],
    }


def _demo_data(
    project_title: str,
    idea: str,
    features: list[str],
    domain: dict[str, Any],
    plan_steps: list[str],
) -> dict[str, Any]:
    queue = []
    priorities = ["High", "Normal", "Low"]
    due_dates = ["today", "tomorrow", "Friday"]
    for index, title in enumerate(domain["sample_titles"]):
        queue.append(
            {
                "id": f"item-{index + 1}",
                "title": title,
                "segment": domain["segments"][index % len(domain["segments"])],
                "owner": domain["owner"] if index == 0 else ["Taylor Kim", "Morgan Diaz"][index - 1],
                "priority": priorities[index],
                "status": domain["workflow"][index],
                "due": due_dates[index],
            }
        )
    return {
        "project": project_title,
        "idea": idea,
        "audience": domain["audience"],
        "record_label": domain["record_label"],
        "workflow_label": domain["workflow_label"],
        "metric_label": domain["metric_label"],
        "workflow": domain["workflow"],
        "features": features,
        "metrics": [
            {"label": "Open items", "value": str(len(queue)), "delta": "2 need attention"},
            {"label": "Response time", "value": "14m", "delta": "from intake to owner"},
            {"label": "On track", "value": "82%", "delta": "target workflow health"},
            {"label": "Blocked", "value": "1", "delta": "waiting on outside input"},
        ],
        "intake_template": {
            "goal": queue[0]["title"],
            "segment": queue[0]["segment"],
            "priority": queue[0]["priority"],
            "owner": domain["owner"],
        },
        "queue": queue,
        "agent_team": [
            {
                "name": "Strategist Agent",
                "role": "Scope and success metric",
                "status": "Ready",
                "output": f"Narrows {domain['workflow_label'].lower()} to one demo path for {domain['audience']}.",
            },
            {
                "name": "Research Agent",
                "role": "Context and constraints",
                "status": "Ready",
                "output": f"Tracks source warnings, domain rules, and {domain['record_label'].lower()} requirements.",
            },
            {
                "name": "Builder Agent",
                "role": "App and API",
                "status": "Ready",
                "output": "Generates the React workspace, FastAPI routes, and database-ready schema.",
            },
            {
                "name": "QA Agent",
                "role": "Risk checks",
                "status": "Ready",
                "output": "Checks queue states, blocked work, and smoke-test coverage before demo.",
            },
            {
                "name": "Demo Agent",
                "role": "Stakeholder narrative",
                "status": "Ready",
                "output": "Packages the walkthrough, API payload, and next implementation steps.",
            },
        ],
        "next_actions": [
            f"Assign an owner and deadline to the newest {domain['record_label'].lower()}.",
            f"Move one item from {domain['workflow'][0].lower()} to {domain['workflow'][1].lower()}.",
            "Review the API response with the frontend before adding persistence.",
        ],
        "implementation_steps": plan_steps,
    }


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
