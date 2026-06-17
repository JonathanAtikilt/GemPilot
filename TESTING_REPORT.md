# GemPilot End-to-End Testing Report

**Date:** 2026-06-16  
**Goal:** Hackathon-demo readiness — fully runnable, presentable, and test-verified.

---

## 1. Repository Overview

| Area | Technology |
|------|------------|
| **Frontend** | Next.js 16.2.6, React 19, TypeScript 5, Tailwind CSS 4 (`frontend/`) |
| **Backend** | Python 3.12+, FastAPI, LangGraph, Uvicorn (`agent/`) |
| **Database / storage** | Supabase Postgres + pgvector (`supabase/migrations/`), in-memory fallbacks for local dev |
| **LLM** | Provider-agnostic facade: Gemini (default), Groq fallback, OpenAI (`agent/llm/provider.py`) |
| **RAG** | Chunking, embeddings, pgvector retrieval (`agent/rag/`) |
| **Tools** | GitHub repo create/commit, build checker (`tools/`) |
| **Package managers** | `pip` + `pyproject.toml` (backend), `npm` (frontend + root stub) |
| **Test framework** | `pytest` + `pytest-asyncio` + `pytest-cov` (backend only; no frontend test runner) |

### Key directories

```
agent/          FastAPI app, LangGraph workflow, RAG, LLM client
frontend/       Mission Control UI (single-page app at app/page.tsx)
tools/          GitHub tool, repo writer, build checker
supabase/       SQL migrations for RAG chunks, memories, GitHub sessions
tests/          177 backend tests
rag/sources/    Local markdown corpus for ingest
```

### Environment variables (from `.env.example`)

| Category | Variables |
|----------|-----------|
| Runtime | `ADAPTER_MODE`, `MOCK_MODE`, `MVPILOT_MOCK_TOOLS`, `ALLOW_IDEA_AWARE_PARTIAL` |
| LLM | `LLM_PROVIDER`, `LLM_MODEL`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, timeout/retry knobs |
| RAG / DB | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| GitHub | `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_REDIRECT_URI`, `GITHUB_TOKEN_ENCRYPTION_KEY`, optional `GITHUB_PERSONAL_ACCESS_TOKEN` |
| Frontend / CORS | `FRONTEND_BASE_URL`, `NEXT_PUBLIC_AGENT_API_URL`, `CORS_ORIGINS` |

### Scripts

| Location | Command | Purpose |
|----------|---------|---------|
| Root `pyproject.toml` | `pytest` | Backend tests (80% coverage gate) |
| `frontend/package.json` | `npm run dev` | Next.js dev server |
| `frontend/package.json` | `npm run build` | Production build + TypeScript check |
| `frontend/package.json` | `npm run lint` | ESLint |
| README | `uvicorn agent.main:app --host 127.0.0.1 --port 3001 --reload` | Backend API |

---

## 2. Setup Steps

### Prerequisites

- Python 3.12+
- Node.js 20+ / npm
- Optional: Supabase CLI for live RAG (`supabase db push`)
- Optional: GitHub OAuth app + LLM API keys for live demo

### Commands used during this audit

```bash
# 1. Recreate Python virtualenv (old venv pointed at deleted NemoPilot path)
cd /Users/jonathanatikilt/Desktop/Projects/GemPilot
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"

# 2. Install frontend dependencies
cd frontend && npm install

# 3. Start backend (mock/demo mode — no live LLM calls)
cd /Users/jonathanatikilt/Desktop/Projects/GemPilot
MOCK_MODE=true ADAPTER_MODE=mock MVPILOT_MOCK_TOOLS=true \
  .venv/bin/uvicorn agent.main:app --host 127.0.0.1 --port 3001

# 4. Start frontend
cd frontend
NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:3001 npm run dev -- --port 3000

# 5. Automated checks
.venv/bin/pytest                    # 177 passed, 83% coverage
.venv/bin/pytest --no-cov -q        # faster iteration
cd frontend && npm run lint
cd frontend && npm run build        # includes TypeScript check
```

### First-time setup (for judges / teammates)

```bash
cp .env.example .env
# Fill GEMINI_API_KEY, SUPABASE_*, GITHUB_OAUTH_* as needed

python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
cd frontend && npm install

# Apply DB migrations (live RAG)
supabase db push

# Terminal 1 — backend
.venv/bin/uvicorn agent.main:app --host 127.0.0.1 --port 3001 --reload

# Terminal 2 — frontend
cd frontend && NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:3001 npm run dev
```

**Offline / classroom demo:** set `MOCK_MODE=true` and `demo_mode: true` on `/agent/run` — completes in ~3s with deterministic artifacts.

---

## 3. Automated Checks

| Check | Command | Result |
|-------|---------|--------|
| Unit + integration tests | `pytest` | **177 passed** |
| Coverage | `pytest` (configured in `pyproject.toml`) | **83.00%** (≥ 80% gate) |
| Frontend lint | `cd frontend && npm run lint` | **Pass** |
| Frontend typecheck | included in `npm run build` | **Pass** |
| Frontend production build | `cd frontend && npm run build` | **Pass** |
| Formatting (ruff/black/prettier) | — | **Not configured** in repo |

### New tests added in this audit

- `tests/test_rag_store_memory.py::test_get_rag_store_reuses_singleton` — verifies RAG store singleton behavior
- `tests/test_agent_api.py::test_orchestrator_start_project_alias_matches_agent_run` — verifies frontend orchestrator entrypoint

---

## 4. Features Tested

### Homepage / navigation

| Feature | Method | Result |
|---------|--------|--------|
| Mission Control loads | `curl http://127.0.0.1:3000/` → HTTP 200 | Pass |
| Branding | HTML contains `GemPilot`, default idea `HealthRef` | Pass |
| No stale copy | No `StudyPilot` or `Person 1` in rendered HTML | Pass (after fix) |
| Responsive layout | Tailwind grid/flex; mobile breakpoints in `page.tsx` | Code review — not browser-automated |

### Authentication (GitHub OAuth)

| Feature | Method | Result |
|---------|--------|--------|
| OAuth config | `GET /api/auth/github/config` | Pass — `oauthConfigured: true` |
| Connection status | `GET /api/auth/github/status` | Pass — `connected: false` when no session |
| Login redirect | `GET /api/auth/github/login` | Not exercised (needs browser + GitHub app) |
| Env PAT fallback | `POST /api/auth/github/use-env-token` | Not exercised (no PAT in env) |

### Form inputs / agent workflow

| Feature | Method | Result |
|---------|--------|--------|
| JSON agent run | `POST /agent/run` with `demo_mode: true` | Pass — task completes in ~3s |
| Multipart intake | Covered by `test_run_agent_accepts_current_frontend_multipart_payload` | Pass |
| Blank idea validation | `POST /agent/run` with empty idea | Pass — HTTP 422 |
| Orchestrator alias | `POST /api/orchestrator/start-project` | Pass |
| Task polling | `GET /agent/tasks/{id}` | Pass — 17 agent steps, status `completed` |
| Live progress steps | `agent_steps` populated incrementally | Pass (progress callback wired) |

### API routes

| Endpoint | Result |
|----------|--------|
| `GET /health` | Pass — reports adapter mode, LLM provider, RAG/GitHub config flags |
| `POST /agent/run` | Pass |
| `GET /agent/tasks/{id}` | Pass |
| `GET /agent/tasks/{missing}` | Pass — HTTP 404 |
| `POST /agent/approve` | Pass (unit tests) |
| `POST /rag/get-build-context` | Pass — 7 deliverables, default tech stack |
| `POST /rag/search` | Pass (unit tests + smoke test in README) |
| `GET /rag/sources` | Pass (unit tests; 503 when Supabase unset) |

### Database reads/writes

| Feature | Result |
|---------|--------|
| RAG chunk storage (Supabase) | Unit-tested; live path requires `SUPABASE_URL` + migrations |
| GitHub connection store | In-memory for local mock run; Supabase-backed when configured |
| Project session store | Unit-tested (`test_project_session_store.py`) |

### File uploads

| Feature | Result |
|---------|--------|
| Multipart file intake on `/agent/run` | Unit-tested (`test_run_agent_accepts_current_frontend_multipart_payload`) |
| GitHub upload API | `POST /api/github/upload-project` — unit-tested via person3 tests |

### AI / LLM features

| Feature | Result |
|---------|--------|
| Mock mode workflow | Pass — full LangGraph pipeline, 76 generated artifacts |
| Gemini structured JSON | Fixed prior to audit (`responseMimeType` + `responseSchema`) |
| Groq fallback | Unit-tested in `test_llm_provider.py` |
| Stack recommendation | `recommend_stack` node + heuristic fallback tested |
| Idea-aware partial output | Config flag `ALLOW_IDEA_AWARE_PARTIAL` — tested |

### GitHub / repository features

| Feature | Result |
|---------|--------|
| Mock repo create/commit | Pass in workflow tests — in-memory tool adapter |
| Live GitHub OAuth | Requires configured OAuth app + user login |
| Duplicate callback routes | **Remaining issue** — both `/github/callback` and `/api/auth/github/callback` exist |

### Demo video generation

| Feature | Result |
|---------|--------|
| Demo artifact pack | Pass — `demo/script.md`, `demo/storyboard.md`, `demo/video_outline.md`, `demo/voiceover.md`, `demo/demo_walkthrough.md` |
| Prompt contract | `test_demo_video_generation_prompt_requires_project_specific_demo_pack` |

### Error / empty / loading states

| State | Result |
|-------|--------|
| Missing task | HTTP 404 with `"Task not found"` |
| Invalid payload | HTTP 422 with Pydantic detail |
| Missing `NEXT_PUBLIC_AGENT_API_URL` | Frontend shows error message (code path reviewed) |
| GitHub not connected on launch | Frontend blocks submit with clear message |
| Workflow failure | `failed` node + frontend `formatWorkflowError` path tested indirectly |

### Browser console / backend logs

| Check | Result |
|-------|--------|
| Backend startup | Clean — Uvicorn on `:3001`, no tracebacks |
| Frontend dev server | Clean — Next.js 16 on `:3000` |
| Agent run logs | 202 Accepted, task polls return 200 |

---

## 5. Bugs Found

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| B1 | **Blocker** | `.venv` pointed at deleted `NemoPilot` path — `pip`/`pytest` unusable | **Fixed** — recreated venv |
| B2 | Medium | `Person 1` hackathon copy still in frontend submit + repo card messages | **Fixed** |
| B3 | Medium | RAG store singleton leaked across tests when env vars removed → flaky `test_sources_requires_supabase` | **Fixed** |
| B4 | Low | No test for `/api/orchestrator/start-project` alias | **Fixed** — new test |
| B5 | Low | No test for RAG store singleton | **Fixed** — new test |
| B6 | Info | Prior audit CRITICAL-1 (Gemini JSON schema) | Already fixed before this audit |
| B7 | Info | Prior audit CRITICAL-2 (`del progress_callback`) | Already fixed — `_fire_progress` wired |
| B8 | Info | Prior audit HIGH-3 (StudyPilot defaults) | Already fixed — `HealthRef` / `GemPilot` |
| B9 | Info | Prior audit HIGH-4 ("Person 1" audit message) | Already fixed in `workflow.py` |
| B10 | Low | Duplicate GitHub OAuth callback routes | **Open** — document redirect URI |
| B11 | Low | `/rag/answer-context` name implies LLM answer but returns chunks only | **Open** — naming/docs |
| B12 | Low | `resolvedTechStack.items` empty when only defaults apply (by design; `defaultItems` populated) | **Open** — acceptable if prompts use full object |
| B13 | Info | No frontend unit/E2E test framework | **Open** |
| B14 | Info | No repo-wide formatter/linter for Python | **Open** |

---

## 6. Bugs Fixed (this audit)

### B1 — Broken virtualenv

Recreated `.venv` at the correct project path and reinstalled `pip install -e ".[test]"`.

### B2 — Stale "Person 1" UI copy

**File:** `frontend/app/page.tsx`

- Submit message now uses `${BRAND_NAME}` instead of "Person 1's orchestrator"
- Repo pending card references GemPilot instead of Person 1

### B3 — RAG store singleton test isolation

**Files:** `agent/rag/store.py`, `tests/conftest.py`

- Added `reset_rag_store()` and module-level singleton cache
- Added `autouse` pytest fixture to reset cache between tests

### B4/B5 — Test coverage gaps

Added orchestrator alias test and singleton reuse test.

---

## 7. Remaining Issues

1. **Live demo requires secrets** — `GEMINI_API_KEY`, Supabase, and GitHub OAuth must be in `.env` for full live path. Use `MOCK_MODE=true` + `demo_mode: true` for offline demos.
2. **GitHub OAuth redirect** — Register exactly `http://127.0.0.1:3001/api/auth/github/callback` in the GitHub app (matches `GITHUB_OAUTH_REDIRECT_URI` in `.env.example`). Legacy `/github/callback` also exists.
3. **Supabase migrations** — Run `supabase db push` before live RAG ingest; re-run `POST /rag/ingest` after embedding-dimension migration.
4. **No frontend automated tests** — Manual UI verification only; consider Playwright for demo regression.
5. **No Python formatter in CI** — Only pytest coverage gate exists.
6. **npm audit warnings** — `npm install` reports dependency advisories; not blocking demo.

---

## 8. Recommended Next Steps

### Before live hackathon demo

1. Copy `.env.example` → `.env` and fill all required keys.
2. Run `supabase db push` then `curl -X POST http://127.0.0.1:3001/rag/ingest`.
3. Connect GitHub via the Mission Control UI before launching a repo build.
4. For the pitch, use a crisp idea (e.g. pre-filled **HealthRef**) and **Hackathon-Winning Project** depth.
5. Verify one live run shows `gemini-2.5-flash` in `agent_steps[].model` (not Groq fallback).

### For production hardening

1. Add Playwright smoke test: load `/`, submit mock build, wait for `completed`.
2. Consolidate GitHub callback to a single route.
3. Add `ruff` + `ruff format --check` to CI.
4. Add frontend test script (Vitest or Playwright component tests).
5. Remove or archive stale `StudyPilot` references in generated-project templates if demos should never mention it.

---

## 9. Demo Readiness Score

**8.5 / 10** (up from prior internal audit of 5/10)

| Area | Status |
|------|--------|
| Mock/offline full workflow | ✅ Ready |
| Frontend build + lint | ✅ Ready |
| Backend tests + coverage | ✅ 177 tests, 83% |
| Live progress streaming | ✅ Fixed |
| Gemini structured JSON | ✅ Fixed |
| Branding / copy | ✅ Fixed |
| Demo video artifact pack | ✅ Generated in workflow |
| GitHub live OAuth + push | ⚠️ Needs configured secrets |
| Live LLM + RAG | ⚠️ Needs API keys + Supabase |
| Frontend automated UI tests | ❌ Not present |

---

## 10. Quick Demo Script

```bash
# Terminal 1
MOCK_MODE=true .venv/bin/uvicorn agent.main:app --host 127.0.0.1 --port 3001

# Terminal 2
cd frontend && NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:3001 npm run dev

# Open http://localhost:3000
# 1. Review pre-filled HealthRef idea
# 2. Click launch (GitHub check skipped in mock — use demo_mode via API for fastest path)
# 3. Watch flight stages populate
# 4. Review generated artifacts, demo/video_outline.md, and build timeline

# Fast API-only demo:
curl -X POST http://127.0.0.1:3001/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"idea":"Build HealthRef healthcare referral app","title":"HealthRef","repo_visibility":"public","demo_mode":true}'
```

---

*Report generated as part of the 2026-06-16 end-to-end audit.*
