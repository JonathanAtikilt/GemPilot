# MVPilot RAG Service

This FastAPI RAG service indexes local markdown/text evidence for the Orchestrator, frontend, and GitHub/build-log agents.

## Install

```bash
python -m pip install -r requirements.txt
```

## Environment

Create `.env` from `.env.example` (or `.env.openclaw.example` on an OpenClaw/Brev backend).

**Required for live RAG** (ingest, search, orchestrator `retrieve_context`):

| Variable | Purpose |
|----------|---------|
| `NVIDIA_API_KEY` | Embeddings + reranking |
| `SUPABASE_URL` | pgvector project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend writes to `rag_chunks` / `memories` |

**Optional:**

| Variable | Purpose |
|----------|---------|
| `NVIDIA_EMBED_MODEL` | Default `llama-nemotron-embed-1b-v2` |
| `NVIDIA_RERANK_MODEL` | Default `llama-nemotron-rerank-1b-v2` |
| `RAG_SCRAPE_URLS` | Comma-separated seed URLs at ingest |
| `NVIDIA_EMBEDDING_URL` / `NVIDIA_RERANK_URL` | Override NIM endpoints |

**OpenClaw deployment:** set the same RAG variables on the OpenClaw host together with `OPENCLAW_API_KEY` and `OPENCLAW_ENV`. Check readiness with `GET /health` — `rag_configured` should be `true` before demoing ingest.

`SUPABASE_SERVICE_ROLE_KEY` is backend-only. Do not expose it through frontend variables.

If required vars are missing, RAG routes and live memory writes return a configuration error.

## Run

```bash
uvicorn agent.main:app --reload --port 3001
```

The server listens on `http://localhost:3001` with this command. Change `--port` if another service is using `3001`.

## Ingest

```bash
curl -X POST http://localhost:3001/rag/ingest
```

The ingester reads `.md` and `.txt` files from:

- `rag/sources/`
- `logs/`

It also scrapes configured web pages (seed URL plus **first-level, same-domain links only**):

- `RAG_SCRAPE_URLS` in `.env` (comma-separated), and/or
- `rag/scrape_urls.txt` (one URL per line)

It chunks documents, embeds chunks with `llama-nemotron-embed-1b-v2` at 2048 dimensions, and stores them in Supabase.

## Search

```bash
curl -X POST http://localhost:3001/rag/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What should MVPilot build first based on hackathon rules?",
    "topK": 5,
    "docTypes": ["hackathon_rules", "nvidia_docs", "build_log"]
  }'
```

Search embeds the query in query mode, retrieves similar chunks, and reranks candidates with `llama-nemotron-rerank-1b-v2` when available.

## Orchestrator integration

The Nemotron workflow always uses live RAG via `LiveRagMemoryAdapter` in the `retrieve_context` node. Results are stored on task state as `build_context` and passed into Nemotron prompts for `scope_mvp` and `plan_repo`.

- Requires `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `NVIDIA_API_KEY`
- Run `POST /rag/ingest` before agent tasks so indexed chunks exist
- No mock defaults or degraded paths: missing config or failed embed/rerank/search raises an error; empty categories mean retrieval found no matching evidence

Direct helper (also used by `POST /rag/get-build-context`):

```python
from agent.rag import get_build_context

context = await get_build_context(
    project_id="demo-project",
    idea="Autonomous hackathon teammate",
    optional_params={"stack": ["FastAPI", "Supabase"], "features": ["RAG", "GitHub"]},
)
```

## Agent Endpoints

- `POST /rag/get-build-context`: Orchestrator calls this before planning. Returns structured deliverables, tools, repo/demo format, tech stack, scope warnings, and evidence.
- `POST /rag/answer-context`: Orchestrator calls this before scope or next-action decisions. It returns context and a short evidence summary, not a final decision.
- `POST /rag/reindex-logs`: GitHub/build-log agent calls this after new commits, build output, or errors.
- `GET /rag/sources`: Frontend calls this to show indexed sources and chunk counts.
- `POST /rag/search`: Frontend and agents call this to show evidence for user questions.

## Supabase

Apply the migrations in `supabase/migrations/` to create `rag_chunks` and `match_rag_chunks`.

Each chunk stores an `authority_score` (0–1) by source type: hackathon rules (1.0) > NVIDIA docs (0.95) > project/architecture docs (0.85) > build logs (0.75) > team notes (0.5). Search ranks by vector similarity multiplied by authority, and reranking applies the same boost.

The table has RLS enabled and no anonymous write policy. For backend inserts, set `SUPABASE_SERVICE_ROLE_KEY` in the server environment only.
