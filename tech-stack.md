# Tech Stack for the NVIDIA OpenClaw + Nemotron Hackathon

## Purpose

This file defines the recommended technical stack for a 4-person team building a deployed autonomous enterprise agent for the NVIDIA OpenClaw + Nemotron hackathon.

The architecture should follow this loop:

```text
Observe -> Retrieve -> Reason -> Act -> Verify -> Remember -> Report
```

The project should not be just a chatbot. The goal is a deployed agent that receives an enterprise event, retrieves context, checks memory, reasons with Nemotron, uses live tools, takes an approved action, verifies the result, stores memory, and shows an audit trail.

---

# 1. Final Recommended Stack

## Core recommendation

```text
Frontend:
  Next.js + TypeScript + Tailwind + Supabase Realtime
  Streamlit as the faster fallback

Agent backend:
  Python + FastAPI + OpenClaw + NVIDIA Nemotron

Database / memory / audit:
  Supabase Postgres

RAG / vector search:
  Supabase Postgres + pgvector

Realtime dashboard updates:
  Supabase Realtime

File storage:
  Supabase Storage, optional for runbooks and uploaded docs

Tool integrations:
  Slack + GitHub + Linear/Jira or mock log API

Deployment:
  Frontend on Vercel
  Agent backend on Brev, Render, Railway, Fly.io, or DGX Spark
  Database on hosted Supabase
```

## Main decision

Yes, Supabase is possible and recommended.

Use Supabase for:

```text
- Persistent memory
- RAG document chunks
- Vector search with pgvector
- Task state
- Tool call logs
- Approval state
- Audit logs
- Realtime dashboard updates
- Optional auth
- Optional file storage
```

Do not use Supabase as the main agent runtime.

The main autonomous agent should run in Python with OpenClaw and Nemotron. Supabase should be the shared backend and source of truth.

---

# 2. High-Level Architecture

```text
User / Judge
   |
   v
Next.js or Streamlit UI
   |
   v
FastAPI Agent Backend
   |
   v
OpenClaw Agent Controller
   |
   +--> NVIDIA Nemotron reasoning
   |
   +--> Supabase RAG retrieval
   |
   +--> Supabase persistent memory
   |
   +--> Tool router
          |
          +--> Slack
          +--> GitHub
          +--> Linear/Jira or mock log API
   |
   v
Verification layer
   |
   v
Supabase audit logs + memory writeback
   |
   v
Realtime dashboard update
```

---

# 3. Technology Ownership Map

| Technology | Primary owner | Used by | Exact use |
|---|---|---|---|
| Python | Person 1 | Person 1, Person 2, Person 3 | Main agent runtime, ingestion scripts, tool wrappers, verification logic |
| FastAPI | Person 1 | Person 1, Person 4 | Agent API endpoints that the frontend calls |
| OpenClaw SDK | Person 1 | Person 1, Person 3 | Agent framework, planner, tool registration, workflow execution |
| NVIDIA Nemotron | Person 1 | Person 1, optionally Person 2 | Planning, reasoning, tool selection, summarization, final reports |
| Custom state machine or LangGraph-style flow | Person 1 | Person 1 | Controls Observe -> Retrieve -> Reason -> Act -> Verify -> Remember -> Report |
| Pydantic | Person 1 | Person 1, Person 2, Person 3 | Shared schemas for tasks, tool calls, approvals, memory records, reports |
| Supabase Postgres | Person 2 | Everyone | Shared database for tasks, memory, docs, tools, approvals, audit logs |
| Supabase pgvector | Person 2 | Person 1, Person 2 | Vector search for RAG and similar memory retrieval |
| Supabase Realtime | Person 4 | Person 4, indirectly everyone | Live UI updates when audit/tool/approval rows change |
| Supabase Storage | Person 2 | Person 2, Person 4 | Optional storage for uploaded runbooks, PDFs, policy docs, seed files |
| Supabase Auth | Person 4 | Person 4, optionally Person 2 | Optional demo login and row-level access story |
| SQL migrations | Person 2 | Person 2 | Defines tables, indexes, pgvector setup, retrieval functions |
| Embedding model | Person 2 | Person 2 | Creates vectors for document chunks and memories |
| Document ingestion scripts | Person 2 | Person 2 | Loads runbooks, policies, prior incidents, and demo data into Supabase |
| Slack API | Person 3 | Person 1, Person 3, Person 4 | Agent sends approved Slack updates and verifies message posted |
| GitHub API | Person 3 | Person 1, Person 3, Person 4 | Agent reads issues/commits or creates/updates GitHub issues |
| Linear/Jira API | Person 3 | Person 1, Person 3, Person 4 | Agent creates or updates tickets and verifies status changes |
| Mock log API | Person 3 | Person 1, Person 3, Person 4 | Demo-safe log search for incident investigation |
| httpx or requests | Person 3 | Person 3 | Python HTTP client for external APIs |
| Next.js | Person 4 | Person 4 | Polished frontend dashboard |
| TypeScript | Person 4 | Person 4 | Frontend type safety and UI logic |
| Tailwind CSS | Person 4 | Person 4 | Fast UI styling |
| shadcn/ui or simple component library | Person 4 | Person 4 | Optional polished components for cards, buttons, modals, timeline |
| Streamlit | Person 4 | Person 4 | Fast fallback frontend if Next.js is too much |
| Vercel | Person 4 | Person 4 | Deploys Next.js frontend |
| Brev / Render / Railway / Fly.io | Person 4 | Person 1, Person 4 | Deploys the Python FastAPI agent backend |
| Docker | Person 4 | Person 1, Person 4 | Packages backend for repeatable deployment |
| Environment variables | Everyone | Everyone | Stores API keys and service URLs safely |
| pytest or basic smoke tests | Everyone | Everyone | Confirms main demo path works before judging |

---

# 4. Person-by-Person Stack

# Person 1 - Agent Orchestration + Nemotron Logic

## Main responsibility

Person 1 owns the agent brain.

They make sure the system behaves like an autonomous workflow instead of a manually driven chatbot.

## Tech used by Person 1

```text
Python
FastAPI
OpenClaw SDK
NVIDIA Nemotron
Pydantic
Supabase Python client
Custom state machine or LangGraph-style flow
```

## What each tech does for Person 1

### Python

Used for the main backend service and agent runtime.

Person 1 writes files like:

```text
agent/main.py
agent/planner.py
agent/state_machine.py
agent/prompts.py
agent/tool_router.py
agent/approval_controller.py
agent/report_generator.py
```

### FastAPI

Used to expose the agent to the frontend.

Recommended endpoints:

```text
POST /agent/run
POST /agent/approve
GET /agent/tasks/{task_id}
GET /health
```

### OpenClaw SDK

Used as the main agent framework.

OpenClaw should coordinate:

```text
- Planner
- Tool router
- RAG retrieval
- Memory lookup
- Action execution
- Verification
- Audit logging
```

### NVIDIA Nemotron

Used for:

```text
- Understanding the incoming task
- Creating the plan
- Choosing which tool to call
- Deciding whether approval is needed
- Summarizing retrieved documents
- Summarizing tool results
- Producing the final report
```

### Pydantic

Used for strict contracts between people.

Example objects:

```text
TaskRequest
AgentStep
RetrievedContext
MemoryMatch
ToolCallRequest
ToolCallResult
ApprovalRequest
VerificationResult
FinalReport
```

### Supabase Python client

Used by Person 1 to read and write shared state.

Person 1 should use Supabase to:

```text
- Create a new task row
- Read retrieved docs and memories
- Write agent steps into audit_logs
- Read approval decisions
- Write final reports
- Trigger memory writeback through Person 2's functions
```

## Person 1 should not own

```text
- Supabase schema design
- Frontend UI design
- Individual tool API wrappers
- Deployment polish
```

They should define contracts and wire the workflow together.

## Person 1 deliverables

```text
- Working OpenClaw agent loop
- Nemotron prompts
- Tool routing logic
- Approval orchestration
- Retry/fallback logic
- Final report generation
- FastAPI endpoints
```

---

# Person 2 - RAG + Persistent Memory

## Main responsibility

Person 2 owns what the agent knows and what it remembers.

They are responsible for the Supabase database, RAG pipeline, vector search, memory retrieval, memory writeback, and audit persistence.

## Tech used by Person 2

```text
Supabase Postgres
pgvector
SQL migrations
Supabase Python client
Python ingestion scripts
Embedding model
Supabase Storage, optional
Supabase Auth/RLS, optional
```

## What each tech does for Person 2

### Supabase Postgres

Used as the main shared database.

Person 2 owns the schema for:

```text
tasks
memories
documents
document_chunks
tool_calls
approvals
audit_logs
```

### pgvector

Used for semantic search over:

```text
- Runbook chunks
- Policy chunks
- Prior incident memories
- Root-cause summaries
```

### SQL migrations

Used to create tables, indexes, and retrieval functions.

Person 2 should create SQL files like:

```text
db/migrations/001_init.sql
db/migrations/002_vector_search.sql
db/migrations/003_seed_demo_data.sql
```

### Embedding model

Used to convert text into vectors.

Use one embedding provider consistently. Good options:

```text
- NVIDIA embedding model through NIM, if available
- sentence-transformers fallback for speed
- Any hackathon-provided embedding endpoint
```

Important rule:

```text
Pick the embedding dimension once and make the Supabase vector column match it.
```

For example:

```sql
embedding vector(1536)
```

or:

```sql
embedding vector(1024)
```

Do not mix dimensions.

### Supabase Storage

Optional. Use it for uploaded docs, runbooks, PDFs, and sample enterprise files.

For a 24-hour hackathon, it is also fine to seed docs from local markdown files.

### Supabase Auth and RLS

Optional for demo credibility.

Use only if it does not slow the team down.

A simple security story is enough:

```text
- Frontend uses public anon key only
- Backend uses service role key only on the server
- Risky actions require approval
- Every action is written to audit_logs
```

## Person 2 database schema

Recommended minimum schema:

```sql
create extension if not exists vector;

create table tasks (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  trigger_text text,
  status text default 'new',
  risk_level text,
  final_report text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table memories (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references tasks(id),
  type text not null,
  entity text,
  summary text not null,
  root_cause text,
  resolution text,
  tools_used jsonb default '[]',
  confidence numeric,
  embedding vector(1536),
  created_at timestamptz default now(),
  last_used_at timestamptz
);

create table documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  source text,
  doc_type text,
  created_at timestamptz default now()
);

create table document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id),
  chunk_text text not null,
  metadata jsonb default '{}',
  embedding vector(1536),
  created_at timestamptz default now()
);

create table tool_calls (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references tasks(id),
  tool_name text not null,
  input_json jsonb,
  output_json jsonb,
  status text,
  verification_status text,
  created_at timestamptz default now()
);

create table approvals (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references tasks(id),
  proposed_action text,
  risk_level text,
  status text default 'pending',
  approved_by text,
  created_at timestamptz default now(),
  resolved_at timestamptz
);

create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references tasks(id),
  step text not null,
  message text,
  data jsonb default '{}',
  created_at timestamptz default now()
);
```

Adjust the vector dimension to match the chosen embedding model.

## Person 2 functions to expose

Person 2 should give Person 1 functions like:

```python
def retrieve_runbooks(query: str, limit: int = 5) -> list[dict]:
    pass


def find_similar_memories(query: str, limit: int = 5) -> list[dict]:
    pass


def write_memory(task_id: str, outcome: dict) -> str:
    pass


def write_audit_log(task_id: str, step: str, message: str, data: dict) -> None:
    pass
```

## Person 2 deliverables

```text
- Supabase schema
- Vector search setup
- Document ingestion pipeline
- Seed runbooks
- Seed previous incidents
- Memory retrieval
- Memory writeback
- Audit log storage
```

---

# Person 3 - Tool Integrations + Verification Layer

## Main responsibility

Person 3 owns the agent's ability to act in the world and prove the action worked.

This person should build fewer integrations but make them reliable.

## Tech used by Person 3

```text
Python
OpenClaw tool wrappers
Pydantic schemas
httpx or requests
Slack API
GitHub API
Linear/Jira API or mock ticket API
Mock log API
Supabase Python client
```

## Recommended tool set

For an incident-response demo, use:

```text
1. Log search tool
2. Ticket update tool
3. Slack notification tool
```

Optional fourth tool:

```text
4. GitHub issue or repo lookup
```

## What each tech does for Person 3

### Python tool wrappers

Each tool should be a small, predictable Python function.

Example files:

```text
tools/log_search_tool.py
tools/slack_tool.py
tools/ticket_tool.py
tools/github_tool.py
tools/verifier.py
tools/policy.py
```

### Pydantic schemas

Used to make tool inputs and outputs predictable.

Example:

```python
class ToolResult(BaseModel):
    tool_name: str
    status: str
    output: dict
    verification_status: str | None = None
    error: str | None = None
```

### Slack API

Used to send an approved incident update.

Verification:

```text
After sending the Slack message, read back the message by timestamp or message ID and confirm it exists.
```

### Ticket API: Linear, Jira, GitHub Issues, or mock

Used to create or update a task/ticket.

Verification:

```text
After updating the ticket, read the ticket again and confirm the field changed.
```

### Mock log API

Use a mock API or local JSON file if real log access is too slow.

This still gives the agent a live-tool pattern:

```text
Agent queries logs -> gets structured result -> reasons about cause -> writes audit log
```

### Supabase Python client

Person 3 should write every tool attempt to:

```text
tool_calls
audit_logs
approvals
```

## Person 3 risk policy

Person 3 should implement the action policy.

```text
Low risk:
  Agent can do automatically.
  Examples: search logs, retrieve docs, classify incident.

Medium risk:
  Requires approval.
  Examples: post Slack message, update ticket status, assign issue.

High risk:
  Agent only recommends.
  Examples: delete data, deploy code, rotate secrets, change production config.
```

## Person 3 deliverables

```text
- 2 to 4 reliable tool integrations
- Tool input/output schemas
- Action execution handlers
- Verification functions
- Retry once on failure
- Approval-safe execution
- Tool audit writes
```

---

# Person 4 - Frontend + Demo Experience + Deployment

## Main responsibility

Person 4 owns what judges see.

This role is not only frontend. This person is also the demo director and deployment owner.

## Tech used by Person 4

Recommended polished option:

```text
Next.js
TypeScript
Tailwind CSS
Supabase JS client
Supabase Realtime
Vercel
```

Fast fallback option:

```text
Streamlit
Supabase Python client
FastAPI backend calls
```

## What each tech does for Person 4

### Next.js

Used to create the main dashboard.

Recommended pages/components:

```text
frontend/app/page.tsx
frontend/components/TriggerForm.tsx
frontend/components/AgentTimeline.tsx
frontend/components/MemoryPanel.tsx
frontend/components/RagPanel.tsx
frontend/components/ToolCallPanel.tsx
frontend/components/ApprovalPanel.tsx
frontend/components/FinalReport.tsx
```

### Supabase Realtime

Used to update the UI as the agent runs.

Subscribe to changes from:

```text
audit_logs
tool_calls
approvals
tasks
```

This lets the dashboard show the autonomous workflow live.

### Supabase JS client

Used by the frontend to:

```text
- Read task status
- Read audit logs
- Read tool calls
- Read approvals
- Subscribe to realtime updates
```

Important security rule:

```text
The frontend should never use the Supabase service role key.
```

### FastAPI calls

The frontend should call the Python backend for agent actions:

```text
POST /agent/run
POST /agent/approve
GET /agent/tasks/{task_id}
```

The frontend should not directly execute tools.

### Vercel

Used to deploy the Next.js app.

### Streamlit fallback

Use Streamlit if the team needs speed over polish.

A Streamlit app can still show:

```text
- Trigger form
- Agent timeline
- Retrieved docs
- Similar memories
- Tool calls
- Approval button
- Verification result
- Final report
```

## Person 4 deliverables

```text
- Working frontend
- Trigger form
- Agent step timeline
- Memory panel
- RAG panel
- Tool call panel
- Approval UI
- Verification display
- Final report view
- Deployment
- Demo script
```

---

# 5. Shared Supabase Tables

| Table | Primary owner | Used by | Purpose |
|---|---|---|---|
| tasks | Person 2 | Everyone | Main task/incident state |
| documents | Person 2 | Person 1, Person 2, Person 4 | Source documents and runbooks |
| document_chunks | Person 2 | Person 1, Person 2 | RAG retrieval chunks |
| memories | Person 2 | Person 1, Person 2, Person 4 | Persistent memory across runs |
| tool_calls | Person 3 | Person 1, Person 3, Person 4 | Tool execution records |
| approvals | Person 3 | Person 1, Person 3, Person 4 | Human approval workflow |
| audit_logs | Person 2 | Everyone | Timeline of agent decisions and actions |

---

# 6. Shared API Contracts

## POST /agent/run

Starts the autonomous workflow.

Request:

```json
{
  "title": "Checkout latency incident",
  "trigger_text": "Checkout latency is above 2 seconds for 15 minutes.",
  "source": "demo_ui"
}
```

Response:

```json
{
  "task_id": "uuid",
  "status": "started"
}
```

## POST /agent/approve

Approves or rejects a pending action.

Request:

```json
{
  "task_id": "uuid",
  "approval_id": "uuid",
  "decision": "approved",
  "approved_by": "demo_judge"
}
```

Response:

```json
{
  "task_id": "uuid",
  "approval_id": "uuid",
  "status": "approved"
}
```

## GET /agent/tasks/{task_id}

Returns the current state of the task.

Response:

```json
{
  "task": {},
  "audit_logs": [],
  "tool_calls": [],
  "approvals": [],
  "memories_used": [],
  "retrieved_documents": []
}
```

---

# 7. Suggested Repository Structure

```text
repo/
  agent/
    main.py
    planner.py
    state_machine.py
    prompts.py
    tool_router.py
    approval_controller.py
    report_generator.py

  tools/
    slack_tool.py
    ticket_tool.py
    log_search_tool.py
    github_tool.py
    verifier.py
    policy.py

  memory/
    retriever.py
    memory_store.py
    embeddings.py
    ingest_docs.py

  db/
    migrations/
      001_init.sql
      002_vector_search.sql
      003_seed_demo_data.sql

  frontend/
    app/
    components/
    lib/

  docs/
    runbooks/
    prior_incidents/
    demo_script.md

  deploy/
    Dockerfile
    docker-compose.yml
    render.yaml

  .env.example
  README.md
  tech-stack.md
```

---

# 8. Environment Variables

Use a `.env.example` file with placeholders only.

```bash
# NVIDIA / Nemotron
NVIDIA_API_KEY=
NEMOTRON_MODEL=

# OpenClaw
OPENCLAW_API_KEY=
OPENCLAW_ENV=

# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Slack
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
SLACK_CHANNEL_ID=

# GitHub
GITHUB_TOKEN=
GITHUB_REPO=

# Linear / Jira / ticketing
LINEAR_API_KEY=
JIRA_BASE_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=

# Logs or mock logs
LOG_API_BASE_URL=

# App
APP_BASE_URL=
AGENT_BACKEND_URL=
```

Security rules:

```text
- SUPABASE_SERVICE_ROLE_KEY is backend-only.
- SLACK_BOT_TOKEN is backend-only.
- GITHUB_TOKEN is backend-only.
- Frontend gets only SUPABASE_ANON_KEY and AGENT_BACKEND_URL.
```

---

# 9. Minimal Demo Path

Build one polished path first.

```text
1. Judge opens dashboard.
2. Judge clicks "Start incident demo".
3. Frontend calls POST /agent/run.
4. Person 1's OpenClaw agent starts task.
5. Agent asks Person 2's retriever for runbooks.
6. Agent asks Person 2's memory store for similar incidents.
7. Agent asks Person 3's log tool for current evidence.
8. Agent reasons with Nemotron.
9. Agent proposes a Slack/ticket update.
10. Approval row is created in Supabase.
11. Person 4's UI shows approval button via Realtime.
12. Judge approves.
13. Agent calls Person 3's Slack/ticket tool.
14. Tool verifies the action worked.
15. Agent writes memory and final report.
16. UI shows final timeline and audit trail.
```

---

# 10. What Each Person Needs From the Others

## Person 1 needs

From Person 2:

```text
- retrieve_runbooks(query)
- find_similar_memories(query)
- write_memory(task_id, outcome)
- write_audit_log(task_id, step, message, data)
```

From Person 3:

```text
- tool registry
- tool input/output schemas
- verification functions
- risk policy
```

From Person 4:

```text
- frontend calls to /agent/run and /agent/approve
- dashboard event expectations
```

## Person 2 needs

From Person 1:

```text
- queries the agent will send
- memory writeback shape
- audit event shape
```

From Person 3:

```text
- tool_call schema requirements
- verification result fields
```

From Person 4:

```text
- tables and fields the UI needs to display
```

## Person 3 needs

From Person 1:

```text
- tool call payloads
- risk level expectations
- retry/fallback behavior
```

From Person 2:

```text
- where to write tool_calls
- where to write audit_logs
- where approvals are stored
```

From Person 4:

```text
- how tool status should appear in the UI
- what approval interaction should look like
```

## Person 4 needs

From Person 1:

```text
- FastAPI endpoint URLs
- task state shape
- final report shape
```

From Person 2:

```text
- Supabase table names
- realtime subscriptions
- fields for RAG and memory display
```

From Person 3:

```text
- tool status labels
- verification result fields
- approval states
```

---

# 11. Build Order

## Hours 0-4: everyone together

```text
- Lock use case
- Lock demo flow
- Lock API contracts
- Lock Supabase schema
- Choose exact tools
- Choose frontend: Next.js or Streamlit
```

## Hours 4-10: parallel build

```text
Person 1:
  Agent loop, FastAPI skeleton, Nemotron prompts

Person 2:
  Supabase schema, seed docs, vector retrieval, memory writeback

Person 3:
  Tool wrappers, verification, policy gates

Person 4:
  UI shell, timeline, approval panel, deployment path
```

## Hours 10-16: integration

```text
- Connect Person 1 to Person 2 retrieval
- Connect Person 1 to Person 3 tools
- Connect Person 4 to FastAPI and Supabase
- Run first full demo
```

## Hours 16-22: hardening

```text
- Fix failures
- Add fallbacks
- Polish audit trail
- Polish final report
- Improve seed data
- Test memory second-run behavior
```

## Hours 22-24: demo polish

```text
- Freeze scope
- Practice demo
- Prepare backup screenshots
- Prepare 3-minute explanation
- Confirm deployment works
```

---

# 12. Recommended MVP Scope

Use this exact scope unless the team is ahead.

```text
Use case:
  Autonomous incident response agent

Trigger:
  Checkout latency alert

RAG:
  Checkout incident runbook

Memory:
  Previous checkout incident caused by payment API timeout

Live tools:
  Log search
  Slack update
  Ticket update

Approval:
  Required before Slack update or ticket update

Verification:
  Confirm Slack message exists
  Confirm ticket status changed

Report:
  Final incident summary with sources, tools, actions, verification, memory stored
```

---

# 13. What Not To Do

Do not do this:

```text
- Do not split into generic frontend/backend/database/AI roles.
- Do not make Supabase run the main agent.
- Do not expose service keys in the frontend.
- Do not build five flaky tools instead of three reliable tools.
- Do not skip verification.
- Do not save memory without retrieving it on the second run.
- Do not make the UI only a chat box.
- Do not wait until the last hour to deploy.
```

---

# 14. Final Role Summary

```text
Person 1:
  Owns the OpenClaw + Nemotron agent brain.
  Uses Python, FastAPI, OpenClaw, Nemotron, Pydantic, Supabase client.

Person 2:
  Owns RAG, memory, Supabase schema, vector search, and audit persistence.
  Uses Supabase Postgres, pgvector, SQL, Python ingestion, embeddings.

Person 3:
  Owns live tools, action execution, verification, and safety policy.
  Uses Python wrappers, Slack/GitHub/Linear/Jira/log APIs, Pydantic, Supabase writes.

Person 4:
  Owns dashboard, approval UI, observability, deployment, and demo story.
  Uses Next.js or Streamlit, Supabase Realtime, Tailwind, Vercel, backend deployment tools.
```

The cleanest stack is:

```text
Supabase = shared state, memory, RAG, approvals, audit, realtime UI
FastAPI = agent API
OpenClaw = agent framework
Nemotron = reasoning model
Python = orchestration and tools
Next.js or Streamlit = dashboard
Slack/GitHub/Jira/log API = live action layer
```
