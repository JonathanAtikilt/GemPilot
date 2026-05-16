# Person 1 Plan: LangGraph + Nemotron Orchestrator

## Summary

Build Person 1's backend as a deployed FastAPI service with LangGraph as the visible orchestration layer and NVIDIA Nemotron via `build.nvidia.com` as the required reasoning model path. This better matches the hackathon page than a custom hidden state machine: judges want a live autonomous agent, multi-step workflows, tool use, persistent memory, and a visible decision process.

Primary stack:

- `Python 3.12`, `FastAPI`, `Uvicorn`
- `LangGraph` for graph orchestration and ReAct-style routing
- `Pydantic v2` and `pydantic-settings` for schemas/config
- `httpx` for NVIDIA endpoint calls
- `pytest`, `pytest-asyncio`, `respx` for tests
- In-memory adapters first for RAG/memory/GitHub until teammates wire real Supabase and GitHub

## Key Changes

- Replace the custom state machine with a `LangGraph StateGraph` as the main orchestrator.
- Keep OpenClaw as an optional adapter/tool boundary, not the first blocking dependency.
- Use `build.nvidia.com`/NVIDIA endpoint access as the primary model path because the hackathon page says NVIDIA endpoints are required for submissions.
- Default model: `nvidia/nemotron-3-super-120b-a12b` for planning/report generation.
- Fast fallback model: `nvidia/nvidia-nemotron-nano-9b-v2` or `nvidia/nemotron-3-nano-30b-a3b` depending on endpoint availability.
- Make the graph trace visible in API responses so Person 4 can show the agent thinking, planning, acting, and verifying.

## Feature Plan

### Feature 1: Backend scaffold

- Create a FastAPI backend with `/health`, `/agent/run`, `/agent/tasks/{task_id}`, and `/agent/approve`.
- Add settings for `NVIDIA_API_KEY`, `NEMOTRON_MODEL`, `NEMOTRON_BASE_URL`, `OPENCLAW_API_KEY`, and adapter mode.
- Add deterministic mock mode so the backend works without external keys during local development.

### Feature 2: LangGraph workflow

- Build a `StateGraph` with nodes: `receive_idea`, `retrieve_context`, `scope_mvp`, `plan_repo`, `create_repo`, `generate_files`, `commit_progress`, `verify_build`, `handle_blocker`, `generate_final_package`, `remember_outcome`, `report_result`.
- Add conditional routing after tool calls: success continues, failure routes to `handle_blocker`, unrecoverable errors route to `failed`.
- Store each node output as an `AgentStep` with `node_name`, `status`, `message`, `model`, `decision_trace`, and `timestamp`.

### Feature 3: Nemotron client

- Implement a `ModelClient` adapter that calls NVIDIA endpoint chat/completions through `httpx`.
- Make every model call return structured JSON for the workflow: MVP scope, repo plan, generated file manifest, blocker analysis, final README, demo script, and pitch.
- Log exact model name and prompt purpose for every reasoning step.
- In mock mode, return fixed healthcare referral outputs that still include realistic Nemotron-style decision traces.

### Feature 4: Adapter contracts

- Add `RagMemoryAdapter` with `retrieve_hackathon_context`, `retrieve_nvidia_context`, `find_similar_builds`, and `write_memory`.
- Add `ToolAdapter` with `create_repo`, `commit_files`, `check_repo_health`, `detect_blocker`, and `verify_commit`.
- Add `AuditAdapter` with `write_audit_log`, `write_tool_call`, and `write_artifact`.
- Start with in-memory implementations; Person 2 and Person 3 can later replace them without changing the graph.

### Feature 5: Demo workflow

- Optimize the first run around the healthcare referral idea already in the docs.
- Generate a scoped MVP with referral input, cardiology policy lookup, missing-document checker, staff approval step, audit log, and pitch page.
- Simulate a verified GitHub flow: repo created, files committed, commit verified.
- Simulate one meaningful blocker: frontend route mismatch, then generate a fix recommendation.
- Final output must include README, build log, demo script, pitch, retrieved sources, memory used, tool calls, verification, and final report.

## Public Interfaces

### `POST /agent/run`

Request:

- `idea`
- `repo_visibility`
- Optional `demo_mode`

Response:

- `task_id`
- `status`

Starts the LangGraph workflow.

### `GET /agent/tasks/{task_id}`

Returns `task`, `agent_steps`, `retrieved_docs`, `memory_matches`, `tool_calls`, `approvals`, `generated_artifacts`, `graph_trace`, and `final_report`.

### `POST /agent/approve`

Request:

- `task_id`
- `approval_id`
- `decision`
- `approved_by`

Included for frontend contract completeness, even if the first demo path does not pause for approval.

### `GET /health`

Returns service status, adapter mode, configured model name, and whether NVIDIA endpoint config is present.

## Test Plan

- Unit test every LangGraph node with mock adapters.
- Test happy path from messy idea to completed final report.
- Test model fallback when NVIDIA endpoint config is missing.
- Test blocker routing when commit verification fails.
- Test API responses include visible `graph_trace` and `decision_trace`.
- Test adapter contracts return the shapes Person 2, Person 3, and Person 4 expect.
- Smoke test full healthcare referral demo in mock mode.

## Assumptions

- Person 1 owns backend orchestration only; RAG storage, real GitHub mutation, and frontend are teammate-owned integrations.
- LangGraph is now the main orchestrator because the Nemotron page highlights LangGraph tutorials, ReAct workflows, and visible agent decision-making.
- NVIDIA `build.nvidia.com` endpoints are the primary model path because the hackathon page says endpoint access is required for submissions.
- OpenClaw remains useful but should not block the first backend pass unless the team already has working SDK examples.
- The first demo should prioritize live functionality and clear graph trace over extra integrations.
- Sources reviewed: `https://www.shortesthack.com/?tab=nemotron`, setup/reminders/submission/resources tabs on the same site, NVIDIA Nemotron RAG/report-generator tutorials, and LangGraph official docs.
