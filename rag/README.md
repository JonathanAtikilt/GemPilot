# NemoPilot RAG Service

The FastAPI RAG service indexes local markdown/text evidence for the Orchestrator, Frontend UI Agent, GitHub Agent, and build-log memory.

## Environment

Create `.env` from the root `.env.example`.

Required for live RAG:

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` or `OPENAI_API_KEY` | Embeddings for ingest, search, and memory writes |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend writes to `rag_chunks` and `memories` |

Optional:

| Variable | Purpose |
|----------|---------|
| `EMBEDDING_PROVIDER` | `gemini` or `openai`; default `gemini` |
| `EMBEDDING_MODEL` | Default `gemini-embedding-001`; use `text-embedding-3-small` for OpenAI |
| `EMBEDDING_DIMENSIONS` | Default `768`; must match Supabase vector columns |
| `RAG_SCRAPE_URLS` | Comma-separated seed URLs at ingest |

`SUPABASE_SERVICE_ROLE_KEY` is backend-only. Do not expose it through frontend variables.

## Run

```bash
uvicorn agent.main:app --reload --port 3001
```

## Ingest

```bash
curl -X POST http://localhost:3001/rag/ingest
```

The ingester reads `.md` and `.txt` files from `rag/sources/` and `logs/`. It also scrapes configured URLs from intake, `.env`, and `rag/scrape_urls.txt`.

It chunks documents, embeds chunks with the configured embedding provider, stores 768-dimensional vectors in Supabase by default, and records source metadata for citations.

## Search

```bash
curl -X POST http://localhost:3001/rag/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What should NemoPilot build first based on project rules?",
    "topK": 5,
    "docTypes": ["hackathon_rules", "build_log"]
  }'
```

Search embeds the query, retrieves similar chunks from pgvector, and ranks by cosine similarity weighted by source authority. External reranking is intentionally disabled for now; `agent/rag/rerank.py` is a local abstraction point for a future cross-encoder.

## Orchestrator Integration

The workflow always uses RAG through `LiveRagMemoryAdapter` in the `retrieve_context` node. Results are stored on task state as `build_context` and passed into structured LLM prompts for `scope_mvp`, `recommend_stack`, and `plan_repo`.

Direct helper:

```python
from agent.rag import get_build_context

context = await get_build_context(
    project_id="demo-project",
    idea="Autonomous hackathon teammate",
    optional_params={"stack": ["FastAPI", "Supabase"], "features": ["RAG", "GitHub"]},
)
```

## Endpoints

- `POST /rag/ingest`
- `POST /rag/search`
- `POST /rag/answer-context`
- `POST /rag/get-build-context`
- `POST /rag/reindex-logs`
- `GET /rag/sources`

## Supabase

Apply the migrations in `supabase/migrations/` to create `rag_chunks`, `memories`, and the pgvector RPC functions.

Each chunk stores an `authority_score` by source type: hackathon rules and required deliverables rank above generated docs, build logs, and team notes. Search returns source, title, doc type, text, similarity, and weighted score for citations.
