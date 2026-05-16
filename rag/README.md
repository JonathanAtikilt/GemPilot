# MVPilot RAG Service

This FastAPI RAG service indexes local markdown/text evidence for the Orchestrator, frontend, and GitHub/build-log agents.

## Install

```bash
python -m pip install -r requirements.txt
```

## Environment

Create `.env` from `.env.example` and set backend secrets only on the server:

```bash
NVIDIA_API_KEY=
NVIDIA_EMBED_MODEL=llama-nemotron-embed-1b-v2
NVIDIA_RERANK_MODEL=llama-nemotron-rerank-1b-v2
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

`SUPABASE_SERVICE_ROLE_KEY` is only for backend-side ingestion/search with the private `rag_chunks` table. Do not expose it through frontend variables.

Supabase is required for RAG storage. If `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` is missing, RAG source listing, ingestion, and search return a configuration error.

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

## Orchestrator helper

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
