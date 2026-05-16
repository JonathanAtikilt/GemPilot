# Person 1 Implementation Plan: Accept Person 2 RAG + Add Persistent Memory

## Summary

Person 1 can accept Person 2's `/rag/get-build-context` work now. The route exists, is mounted under `/rag`, and the orchestrator already uses the same build-context logic through `LiveRagMemoryAdapter`.

The remaining integration work is persistent memory. Person 2 still needs a Supabase-backed `memories` table, and Person 1 needs to call `write_memory()` from the `remember_outcome` graph node.

## Key Changes

- Accept Person 2's current RAG handoff:
  - Use existing `POST /rag/get-build-context`.
  - Keep Person 1 calling RAG through `LiveRagMemoryAdapter.retrieve_build_context()`.
  - Do not add direct Supabase or HTTP RAG calls inside `workflow.py`.

- Add a Supabase migration for `public.memories`:
  - `id uuid primary key default gen_random_uuid()`
  - `task_id uuid references public.tasks(id) on delete set null`
  - `idea text not null`
  - `summary text not null`
  - `outcome jsonb default '{}'::jsonb`
  - `tags text[] default '{}'::text[]`
  - `embedding extensions.vector(2048)`
  - `created_at timestamptz default now()`
  - Enable RLS.
  - Add indexes for `task_id`, `created_at desc`, and vector search.
  - Add RPC `match_memories(query_embedding extensions.vector(2048), match_count int default 5)`.

- Add a Supabase memory store:
  - `write_memory(memory)` embeds the summary using existing NVIDIA embedding logic and inserts into `memories`.
  - `search_memories(query, top_k)` embeds the query and calls `match_memories`.
  - Return memory matches with `id`, `task_id`, `idea`, `summary`, `outcome`, `tags`, `similarity`, `score`, and `created_at`.

- Wire memory through existing adapter methods:
  - Update `LiveRagMemoryAdapter.find_similar_builds()` to read from `memories`.
  - Update `LiveRagMemoryAdapter.write_memory()` so it is no longer a no-op.
  - Keep the `RagMemoryAdapter` interface stable.

- Update the orchestrator remember step:
  - Make `remember_outcome` async.
  - Build a memory payload from `task_id`, `idea`, `mvp_scope`, `repo_plan`, `blocker_analysis`, `generated_artifacts`, and `final_report`.
  - Call `active_retrieval.write_memory(payload)`.
  - Keep the graph node name `remember_outcome`.

## Public Interfaces

- No change to `POST /agent/run`.
- No change to `GET /agent/tasks/{task_id}`.
- `memory_matches` remains `list[dict]`.
- Frontend should keep reading memory evidence through `GET /agent/tasks/{task_id}`, not direct Supabase access.
- Backend env vars required for live RAG and memory:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `NVIDIA_API_KEY`

## Test Plan

- Add a migration test confirming `public.memories`, RLS, indexes, and `match_memories` exist.
- Add unit tests for memory insert with mocked Supabase client and mocked `embed_text`.
- Add unit tests for memory search result shaping.
- Update `test_live_adapters.py` so `write_memory()` verifies a real store call.
- Add a workflow test proving `remember_outcome` calls `write_memory()` and the task still completes.
- Add a second-run test where `find_similar_builds()` returns a prior memory and `memory_matches` appears in task detail.
- Run backend tests:

```cmd
if not exist .tmp_pytest mkdir .tmp_pytest && set TMP=%CD%\.tmp_pytest&& set TEMP=%CD%\.tmp_pytest&& pytest
```

## Assumptions

- Use this new doc file instead of overwriting `docs/person1/plan.md`.
- Service-role backend access is enough for v1; no frontend Supabase policy for `memories` yet.
- Memory embeddings use the same 2048-dimension NVIDIA embedding model as RAG chunks.
- Missing Supabase or NVIDIA config should fail clearly in live mode, matching current RAG behavior.
