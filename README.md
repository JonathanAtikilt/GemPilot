# GemPilot

GemPilot takes a project idea and produces a complete, demo-ready full-stack GitHub repository by running it through a LangGraph orchestration pipeline backed by Gemini (or Groq/OpenAI as fallback).

## Overview

The problem GemPilot solves is that generating code from an LLM in a single shot produces a disconnected pile of files — wrong imports, placeholder content, no seed data, no demo materials, no architecture doc. GemPilot runs the process as a phased state machine: scope the idea, recommend a stack, plan the repository layout, generate files in passes, validate the output against 22 checks, then commit the result to GitHub through backend OAuth.

The pipeline is built on LangGraph. Each phase is a node in a typed state graph. The nodes share a mutable state object that accumulates the plan, the generated artifacts, tool call logs, and build timeline events. The frontend polls a task ID for live telemetry while the backend works.

RAG is wired in at the context-gathering phase. If the user supplies a reference URL or uploads files, the backend scrapes and chunks them, embeds using Gemini or OpenAI embeddings, stores vectors in Supabase pgvector, and retrieves the top-k chunks as grounding context before the LLM writes the plan. This is what keeps the generated stack from ignoring domain-specific constraints in the project brief.

## Architecture

```
User (browser)
    |
    | form submit (multipart/form-data)
    v
Next.js frontend (port 3000)
    |
    | POST /api/orchestrator/start-project
    v
FastAPI backend (port 3001)
    |
    |-- GitHub OAuth session store (encrypted token, Supabase)
    |
    v
LangGraph workflow
    |
    |-- scope_mvp       → MvpScopeOutput (requirements, features, api_routes)
    |-- recommend_stack → RecommendedStackOutput (frontend, backend, db, auth)
    |-- plan_repo       → RepoPlanOutput (file tree, implementation steps)
    |-- generate_files  → run_staged_generation() → artifact list
    |     |
    |     |-- Pass 1: __init__ files and package stubs
    |     |-- Pass 2: all priority paths (App.jsx, main.py, schema, docs ...)
    |     |-- Pass 3: orphan import cleanup
    |
    |-- validate_output → validate_project_output() (22 checks)
    |-- commit_repo     → GitHub tool (create repo, commit files, verify)
    |-- finalize        → final_report with links, delivery summary
    |
    v
Supabase (task persistence, pgvector for RAG)
    |
    v
GitHub (generated repository)
    |
    v
GET /agent/tasks/:id  ← frontend polls every 1.5 s
    |
    v
Mission Control UI (build timeline, activity log, validation checks, repo link)
```

Each layer:

- **Frontend (Next.js + Tailwind)**: single-page Mission Control. Handles GitHub OAuth redirect, live task polling, and displays build telemetry, RAG evidence chunks, tool call history, and the final repo link.
- **FastAPI backend**: receives the intake form, stores tasks in Supabase, runs the LangGraph workflow in a background task, and hosts the GitHub OAuth callback route.
- **LangGraph workflow** (`agent/workflow.py`): typed `StateGraph` where each node reads from and writes to a shared `WorkflowState`. Nodes emit `AgentStep` events that the poller streams to the UI.
- **LLM provider facade** (`agent/llm/provider.py`): wraps Gemini, Groq, and OpenAI behind a single interface. Structured JSON calls use function calling or JSON mode depending on the provider. Groq is used as a low-latency fallback for structured calls when `GROQ_API_KEY` is set.
- **RAG layer** (`agent/rag/`): scrape → chunk → embed → pgvector store → retrieve. `build_context.py` assembles the retrieved chunks into a `BuildContext` passed to the planner.
- **Code generator** (`agent/code_generator.py`, `agent/project_generation.py`): three-pass staged generation. Pass 1 creates `__init__.py` and package stubs so later imports resolve. Pass 2 generates all priority paths. Pass 3 runs import repair to remove or fix references to missing modules.
- **Validation** (`agent/project_validation.py`): 22 named checks covering title match, UI specificity, feature count, architecture doc coverage, API/DB planning, auth flow, file completeness, import resolution, frontend routes, backend routes, database model usage, README quality, demo materials, seed data, and degraded-mode disclosure.
- **GitHub tool** (`tools/github_tool.py`): creates or updates a repo, commits the artifact tree as a single commit, then health-checks the push.

## Technical decisions

- **LangGraph for orchestration**: a directed graph makes it straightforward to add checkpoints, retry individual nodes, and attach human-in-the-loop approval steps without rewriting the control flow. The typed `WorkflowState` makes inter-node data explicit rather than passing loose dicts through function calls.

- **3-pass import repair**: LLMs frequently generate imports that reference modules not present in the output. The three-pass approach (init/stub files first, priority files second, orphan removal third) means by the time validation runs, local Python and JS imports have a real chance of resolving. This is why `imports_resolve` is one of the 22 validation checks rather than an afterthought.

- **22-check validation**: the checks span the full output — not just "did files appear" but "does the README reflect the idea", "do backend routes match the planned API routes", "are database models actually imported by the backend entry point", "are demo materials specific to the project idea". This catches the common failure mode of LLMs generating plausible-looking but project-agnostic boilerplate.

- **Supabase for task persistence**: storing task state in Supabase means the frontend can poll `/agent/tasks/:id` across page reloads and browser sessions without the backend holding in-memory state. The same Supabase project provides pgvector for RAG storage, which keeps infrastructure simple.

- **Gemini 2.5 Flash as default**: cost-effective for the large-context calls needed at the repo-planning and file-generation phases. The provider facade makes it straightforward to swap in a different model per call — for example, using Groq's Llama models for fast structured JSON extraction where latency matters more than raw output quality.

- **Backend-side GitHub OAuth**: the GitHub token is encrypted with Fernet and stored server-side. The frontend only holds a `github_connection_id` opaque string in sessionStorage. This keeps credentials out of the browser and makes it safe to pass the connection ID in form data without exposing the actual token.

## Features

What works:

- Full LangGraph orchestration pipeline from idea to committed GitHub repository
- Provider-agnostic LLM calls (Gemini, Groq, OpenAI) with structured JSON output and retries
- RAG pipeline: URL scraping, chunking, Gemini/OpenAI embeddings, pgvector retrieval
- Three-pass staged code generation with import repair
- 22-check validation with per-check pass/fail detail surfaced in the UI
- GitHub OAuth (create new repo or push to existing repo)
- Live Mission Control UI with build timeline, activity log, RAG evidence, and tool call history
- Task persistence across page reloads via Supabase
- Degraded-mode fallback (idea-aware partial output when LLM calls time out)

What requires live API keys to function:

- LLM calls: `GEMINI_API_KEY` (or `GROQ_API_KEY` / `OPENAI_API_KEY`)
- RAG vector storage: `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`
- GitHub repo creation: `GITHUB_OAUTH_CLIENT_ID` + `GITHUB_OAUTH_CLIENT_SECRET` + `GITHUB_TOKEN_ENCRYPTION_KEY`

Without API keys, the backend starts and the frontend loads, but task submission will fail at the LLM or GitHub steps.

## Project structure

```
GemPilot/
├── agent/                  # FastAPI app and LangGraph pipeline
│   ├── main.py             # FastAPI entry point, router registration
│   ├── workflow.py         # LangGraph StateGraph: nodes and edges
│   ├── orchestrator.py     # Phase/plan/timeline helpers
│   ├── code_generator.py   # Three-pass staged generation
│   ├── project_generation.py  # Artifact merging, import repair
│   ├── project_validation.py  # 22-check validation
│   ├── model_client.py     # Pydantic model client, mock/live modes
│   ├── llm/
│   │   └── provider.py     # Gemini/Groq/OpenAI facade
│   ├── rag/                # Scrape, chunk, embed, store, retrieve
│   ├── routers/            # FastAPI route handlers (agent, github, health)
│   ├── github_oauth.py     # OAuth flow, token encryption
│   └── schemas.py          # Shared Pydantic schemas
├── frontend/               # Next.js app
│   └── app/
│       └── page.tsx        # Mission Control UI (single page)
├── rag/
│   ├── sources/            # Local markdown corpus for ingest
│   └── README.md           # RAG API and ingest notes
├── tools/                  # GitHub export, build checker, policy layer
├── supabase/               # Migrations and local Supabase config
├── tests/                  # pytest test suite
├── .env.example            # All required and optional env vars
└── requirements.txt        # Python dependencies
```

## Setup

Prerequisites:

- Python 3.12+
- Node.js 18+
- A Supabase project (for task persistence and RAG vector storage)
- A Gemini API key (or Groq/OpenAI)
- A GitHub OAuth App (for repo creation)

Steps:

1. Clone the repository.

2. Create a Python virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

4. Copy the example env file and fill in your values:

   ```bash
   cp .env.example .env
   ```

5. Start the backend:

   ```bash
   .venv/bin/uvicorn agent.main:app --host 127.0.0.1 --port 3001 --reload
   ```

6. Start the frontend (in a separate terminal):

   ```bash
   cd frontend
   NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:3001 npm run dev
   ```

   Open http://localhost:3000.

To enable RAG, run the ingest endpoint after the backend is up:

```bash
curl -X POST http://127.0.0.1:3001/rag/ingest
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes (if using Gemini) | Primary LLM and default embedding provider |
| `GROQ_API_KEY` | No | Optional fallback for structured JSON calls |
| `OPENAI_API_KEY` | No | Optional; required if `LLM_PROVIDER=openai` or `EMBEDDING_PROVIDER=openai` |
| `LLM_PROVIDER` | No | `gemini` (default), `groq`, or `openai` |
| `LLM_MODEL` | No | Defaults to `gemini-2.5-flash` |
| `EMBEDDING_PROVIDER` | No | `gemini` (default) or `openai` |
| `EMBEDDING_MODEL` | No | Defaults to `gemini-embedding-001` |
| `EMBEDDING_DIMENSIONS` | No | Defaults to `768` |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `GITHUB_OAUTH_CLIENT_ID` | Yes (for GitHub) | GitHub OAuth app client ID |
| `GITHUB_OAUTH_CLIENT_SECRET` | Yes (for GitHub) | GitHub OAuth app client secret |
| `GITHUB_OAUTH_REDIRECT_URI` | Yes (for GitHub) | Must match OAuth app callback URL |
| `GITHUB_TOKEN_ENCRYPTION_KEY` | Yes (for GitHub) | Fernet key; generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `FRONTEND_BASE_URL` | No | Defaults to `http://localhost:3000` |
| `NEXT_PUBLIC_AGENT_API_URL` | Yes | Backend URL the browser sends requests to |
| `CORS_ORIGINS` | No | JSON array of allowed origins |
| `ADAPTER_MODE` | No | `live` (default) or `mock` |
| `ALLOW_IDEA_AWARE_PARTIAL` | No | Set `true` to allow degraded partial output on LLM timeout |

## Running tests

```bash
.venv/bin/pytest tests/ -q
```

For lint on the frontend:

```bash
cd frontend && npm run lint
```

## Known limitations

- The full pipeline takes several minutes per run; LLM timeouts are configured conservatively and can be adjusted in `.env`.
- RAG retrieval only runs if `SUPABASE_URL` and the embedding provider key are set and the ingest endpoint has been called at least once.
- GitHub repo creation requires the OAuth app to have the `repo` scope. If the connected user's token lacks write access to the target org, the commit step will fail with an error surfaced in Mission Control.
- Generated projects target a specific opinionated file layout (Vite+React frontend, FastAPI backend). Projects that need a different structure (e.g., Next.js fullstack or Express) will work but may require manual adjustments.
- The `studypilot_benchmark_complete` validation check fires if the submitted idea resembles a study app; this is a benchmark leftover and does not affect other project types.

## Future work

- Add a human-in-the-loop checkpoint after the plan phase so users can edit the feature list and stack before code generation starts.
- Parallelize the file generation passes using LangGraph's parallel node execution to reduce wall-clock generation time.
- Add a streaming endpoint so the frontend can receive build output as it is generated rather than polling on a 1.5-second interval.
- Extend the import repair pass to cover TypeScript path aliases declared in `tsconfig.json` so the `imports_resolve` check is accurate for all generated frontend structures.
- Add a re-run mode that takes an existing task ID and regenerates only the files that failed validation, rather than restarting the full pipeline.
