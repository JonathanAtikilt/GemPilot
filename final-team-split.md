# Final Team Split for MVPilot

## Project Target

MVPilot is an autonomous hackathon teammate that turns a messy project idea into a working MVP from scratch.

The demo should show this flow:

```text
Messy idea
-> GitHub repo creation
-> RAG over hackathon and NVIDIA docs
-> MVP scoping
-> Codebase generation
-> Step-by-step commits
-> Build log and blocker detection
-> Fix or recommendation
-> Final README, demo script, and pitch
```

The architecture should follow the enterprise agent loop:

```text
Observe -> Retrieve -> Reason -> Act -> Verify -> Remember -> Report
```

The team's job is not to build a generic chatbot. The goal is a deployed agent workflow that visibly uses OpenClaw, Nemotron, RAG, GitHub tools, persistent state, verification, and an audit trail.

---

## Final 4-Person Ownership

| Member | Role | Owns | Main Output |
|---|---|---|---|
| Person 1 | Agent Orchestration + Nemotron Logic | MVPilot brain, workflow state machine, OpenClaw runtime, Nemotron reasoning | Working agent backend that drives the whole build loop |
| Person 2 | RAG + Memory + Supabase | Docs ingestion, vector retrieval, project memory, audit persistence | Reliable knowledge and memory layer for the agent |
| Person 3 | GitHub + Tool Actions + Verification | Repo creation, file commits, tool wrappers, blocker checks, verification | Real actions with proof they worked |
| Person 4 | Frontend + Demo + Deployment | Dashboard, live timeline, approval/demo flow, final pitch experience | Judge-facing app and polished demo path |

This split is based on workflow ownership, not generic frontend/backend/database roles. Each person owns a visible part of the autonomous loop.

---

# Person 1 - Agent Orchestration + Nemotron Logic

## Mission

Person 1 owns the MVPilot brain.

They make sure MVPilot behaves like an autonomous builder that can take a messy idea, decide what to do next, call the right tools, react to blockers, and produce final artifacts.

## Architecture Ownership

Person 1 owns these parts of the loop:

```text
Observe
Reason
Plan
Coordinate
Policy decisions
Final report generation
```

## Tech Stack

```text
Python
FastAPI
OpenClaw
NVIDIA Nemotron
Pydantic
Supabase Python client
Custom state machine
```

## Main Files To Build

Recommended structure:

```text
agent/
  main.py
  state_machine.py
  planner.py
  prompts.py
  tool_router.py
  approval_controller.py
  report_generator.py
  schemas.py
```

## Required Backend Endpoints

Person 1 should expose these FastAPI endpoints:

```text
POST /agent/run
POST /agent/approve
GET /agent/tasks/{task_id}
GET /health
```

### POST /agent/run

Starts a new MVPilot run from a messy idea.

Request:

```json
{
  "idea": "Build a healthcare referral coordination agent that helps clinics prevent failed referrals.",
  "repo_visibility": "public"
}
```

Response:

```json
{
  "task_id": "uuid",
  "status": "started"
}
```

### POST /agent/approve

Approves an action if the workflow needs human confirmation.

Request:

```json
{
  "task_id": "uuid",
  "approval_id": "uuid",
  "decision": "approved",
  "approved_by": "judge"
}
```

### GET /agent/tasks/{task_id}

Returns all current state for the dashboard.

Response should include:

```text
task
agent_steps
retrieved_docs
tool_calls
approvals
build_logs
generated_artifacts
final_report
```

## Agent State Machine

Person 1 should implement the main flow as explicit states:

```text
received_idea
created_task
retrieved_context
scoped_mvp
planned_repo
created_repo
generated_files
committed_progress
checked_build
handled_blocker
generated_final_package
completed
failed
```

Each state should:

1. Write an audit log row.
2. Call Person 2 or Person 3 when needed.
3. Return structured state for Person 4's UI.
4. Fail with a useful message instead of silently stopping.

## Nemotron Responsibilities

Use Nemotron for:

```text
- Cleaning up the messy idea
- Scoping the idea into a realistic MVP
- Choosing the first generated file structure
- Summarizing retrieved hackathon/NVIDIA docs
- Deciding which tool call comes next
- Explaining blockers
- Generating the final README
- Generating the final pitch
- Generating the demo script
```

## Prompt Modules

Person 1 should keep prompts in one place:

```text
agent/prompts.py
```

Recommended prompt names:

```text
SCOPE_MVP_PROMPT
PLAN_REPO_PROMPT
GENERATE_FILE_TREE_PROMPT
BLOCKER_ANALYSIS_PROMPT
FINAL_README_PROMPT
DEMO_SCRIPT_PROMPT
PITCH_PROMPT
```

## Contracts Needed From Other Members

From Person 2:

```python
retrieve_hackathon_context(query: str, limit: int = 5) -> list[dict]
retrieve_nvidia_context(query: str, limit: int = 5) -> list[dict]
find_similar_builds(query: str, limit: int = 3) -> list[dict]
write_memory(task_id: str, summary: dict) -> str
write_audit_log(task_id: str, step: str, message: str, data: dict) -> None
```

From Person 3:

```python
create_repo(repo_name: str, description: str, visibility: str) -> dict
commit_files(repo_name: str, files: list[dict], message: str) -> dict
check_repo_health(repo_name: str) -> dict
detect_blocker(logs: list[dict]) -> dict
verify_commit(repo_name: str, commit_sha: str) -> dict
```

From Person 4:

```text
- Exact frontend request body for /agent/run
- Approval UI expected states
- Timeline fields needed for display
- Final report shape needed for demo
```

## Person 1 Deliverables

By integration time, Person 1 must provide:

```text
- Running FastAPI backend
- OpenClaw-driven workflow skeleton
- Nemotron prompt calls
- State machine with clear step names
- Tool router that can call Person 2 and Person 3 modules
- Final report generator
- Error handling for failed retrieval, failed tool calls, and failed commits
```

## Acceptance Checklist

Person 1 is done when:

```text
- /health returns OK
- /agent/run creates a task and starts the workflow
- The workflow writes visible audit logs
- The workflow can call the RAG layer
- The workflow can call the GitHub/tool layer
- The workflow can finish with a final README, demo script, and pitch
- A failed tool call becomes a visible blocker instead of a crash
```

---

# Person 2 - RAG + Memory + Supabase

## Mission

Person 2 owns what MVPilot knows and what it remembers.

They build the Supabase schema, document ingestion, vector search, persistent memory, and audit storage. This is what lets the demo say: MVPilot scoped the build using hackathon/NVIDIA docs and learned from previous runs.

## Architecture Ownership

Person 2 owns these parts of the loop:

```text
Retrieve
Remember
Audit storage
Context grounding
Memory writeback
```

## Tech Stack

```text
Supabase Postgres
pgvector
Supabase Python client
SQL migrations
Python ingestion scripts
NVIDIA embedding model or fallback embedding model
Supabase Realtime support
```

## Main Files To Build

Recommended structure:

```text
db/
  migrations/
    001_init.sql
    002_vector_search.sql
    003_seed_demo_data.sql

memory/
  embeddings.py
  ingest_docs.py
  retriever.py
  memory_store.py
  audit_log.py
  seed_data.py

docs/
  hackathon/
  nvidia/
  sample_projects/
```

## Database Tables

Minimum Supabase tables:

```text
tasks
documents
document_chunks
memories
tool_calls
approvals
audit_logs
generated_artifacts
```

## Recommended Schema

Use this as the starting point. Adjust the vector dimension to match the chosen embedding model.

```sql
create extension if not exists vector;

create table tasks (
  id uuid primary key default gen_random_uuid(),
  idea text not null,
  repo_name text,
  status text default 'new',
  scoped_mvp text,
  final_report text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
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

create table memories (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references tasks(id),
  type text not null,
  summary text not null,
  successful_pattern text,
  failed_attempts jsonb default '[]',
  tools_used jsonb default '[]',
  embedding vector(1536),
  confidence numeric,
  created_at timestamptz default now(),
  last_used_at timestamptz
);

create table tool_calls (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references tasks(id),
  tool_name text not null,
  input_json jsonb default '{}',
  output_json jsonb default '{}',
  status text,
  verification_status text,
  created_at timestamptz default now()
);

create table approvals (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references tasks(id),
  proposed_action text not null,
  risk_level text not null,
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

create table generated_artifacts (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references tasks(id),
  artifact_type text not null,
  path text,
  content text,
  commit_sha text,
  created_at timestamptz default now()
);
```

## Documents To Seed

Person 2 should seed a small but strong knowledge base:

```text
Hackathon rules
Judging criteria
OpenClaw setup notes
Nemotron model notes
NemoClaw safety notes, if used
GitHub repo requirements
MVPilot project idea
Sample generated project README
Sample build logs
```

If real docs are slow to ingest, use short markdown files with the exact facts needed for the demo.

## Retrieval Functions

Person 2 should expose these functions for Person 1:

```python
def retrieve_hackathon_context(query: str, limit: int = 5) -> list[dict]:
    pass


def retrieve_nvidia_context(query: str, limit: int = 5) -> list[dict]:
    pass


def find_similar_builds(query: str, limit: int = 3) -> list[dict]:
    pass


def write_memory(task_id: str, summary: dict) -> str:
    pass


def write_audit_log(task_id: str, step: str, message: str, data: dict) -> None:
    pass
```

## Retrieval Output Shape

Every retrieved chunk should look like:

```json
{
  "title": "Hackathon judging criteria",
  "source": "docs/hackathon/judging.md",
  "chunk_text": "Projects should demonstrate OpenClaw, Nemotron, persistent memory, live tools, and verification.",
  "score": 0.87,
  "metadata": {
    "doc_type": "hackathon_rules"
  }
}
```

## Memory Demo Requirement

The strongest demo moment is a second run.

First run:

```text
MVPilot builds a referral-agent MVP and stores what worked.
```

Second run:

```text
MVPilot receives a similar healthcare workflow idea, retrieves the previous build memory, and scopes faster with better defaults.
```

The UI should show:

```text
Memory used: Similar build from earlier run
Successful pattern: RAG + missing-document checker + approval flow
```

## Person 2 Deliverables

By integration time, Person 2 must provide:

```text
- Supabase project
- SQL migrations
- Seed docs
- Working document ingestion
- Working vector search
- Similar build memory retrieval
- Memory writeback
- Audit log helper
- Table names and field names for frontend subscriptions
```

## Acceptance Checklist

Person 2 is done when:

```text
- The database can be created from migrations
- Seed docs are loaded
- A query returns relevant chunks
- A task can write audit logs
- A completed run can write memory
- A second run can retrieve prior memory
- Person 4 can subscribe to task/audit/tool tables
```

---

# Person 3 - GitHub + Tool Actions + Verification

## Mission

Person 3 owns MVPilot's ability to act in the world and prove the action worked.

For this project, GitHub is the main live tool. Person 3 should make repo creation, file generation commits, build log commits, blocker detection, and verification reliable.

## Architecture Ownership

Person 3 owns these parts of the loop:

```text
Act
Verify
Tool safety
GitHub execution
Blocker detection
```

## Tech Stack

```text
Python
GitHub API
OpenClaw tool wrappers
Pydantic
httpx or requests
Supabase Python client
Optional Slack API
Optional mock build runner
```

## Main Files To Build

Recommended structure:

```text
tools/
  github_tool.py
  repo_writer.py
  file_generator.py
  build_checker.py
  blocker_detector.py
  verifier.py
  policy.py
  schemas.py
```

## Required Tools

Person 3 should implement these as clean Python functions.

### create_repo

Creates the generated MVP repository.

```python
def create_repo(repo_name: str, description: str, visibility: str) -> dict:
    pass
```

Returns:

```json
{
  "repo_name": "referral-agent-mvp",
  "repo_url": "https://github.com/user/referral-agent-mvp",
  "status": "created"
}
```

### commit_files

Creates or updates files in the generated repo.

```python
def commit_files(repo_name: str, files: list[dict], message: str) -> dict:
    pass
```

Input file shape:

```json
{
  "path": "README.md",
  "content": "# Referral Agent MVP"
}
```

Returns:

```json
{
  "commit_sha": "abc123",
  "message": "Add initial project scaffold",
  "files_changed": 5,
  "status": "committed"
}
```

### append_build_log

Writes a visible build log.

```python
def append_build_log(task_id: str, repo_name: str, message: str, data: dict) -> dict:
    pass
```

The generated repo should include:

```text
logs/build_log.md
```

Example log:

```text
10:05 - Created GitHub repo referral-agent-mvp
10:08 - Added README and package setup
10:15 - Added sample cardiology policy
10:25 - Added RAG retrieval workflow
10:40 - Detected route mismatch
10:45 - Fixed frontend API route
```

### check_repo_health

Checks whether the generated repo has the expected files.

```python
def check_repo_health(repo_name: str) -> dict:
    pass
```

Minimum checks:

```text
README.md exists
logs/build_log.md exists
demo/demo_script.md exists
package or requirements file exists
source folder exists
at least one commit exists after scaffold
```

### detect_blocker

Turns errors into demo-ready blocker records.

```python
def detect_blocker(logs: list[dict]) -> dict:
    pass
```

Example output:

```json
{
  "has_blocker": true,
  "blocker_type": "route_mismatch",
  "summary": "Frontend called /api/analyze but backend exposes /api/analyze-referral.",
  "recommended_fix": "Update frontend fetch call to /api/analyze-referral."
}
```

### verify_commit

Confirms that a GitHub action actually happened.

```python
def verify_commit(repo_name: str, commit_sha: str) -> dict:
    pass
```

Returns:

```json
{
  "commit_sha": "abc123",
  "verified": true,
  "files_changed": ["README.md", "logs/build_log.md"]
}
```

## Safety Policy

Person 3 should keep tool actions controlled.

```text
Low risk:
  Read repo data, inspect files, summarize logs.

Medium risk:
  Create repo, commit generated files, post demo Slack message.
  These can run automatically for the hackathon demo, but they must be logged.

High risk:
  Delete repo, change secrets, modify unrelated repos, force-push, rewrite history.
  MVPilot should refuse or ask for explicit approval.
```

## GitHub Scope

Use a dedicated generated repo name. Do not let MVPilot modify the MVPilot source repo during the demo.

Recommended generated repo pattern:

```text
mvpilot-generated-{short-id}
```

Example:

```text
mvpilot-generated-referral-agent
```

## Tool Call Logging

Every tool call should write to Supabase:

```text
tool_calls
audit_logs
generated_artifacts
```

Minimum fields:

```text
task_id
tool_name
input_json
output_json
status
verification_status
created_at
```

## Person 3 Deliverables

By integration time, Person 3 must provide:

```text
- GitHub repo creation tool
- Commit files tool
- Build log writer
- Commit verifier
- Repo health checker
- Blocker detector
- Tool schemas
- Risk policy
- Test/mock mode for demo safety
```

## Acceptance Checklist

Person 3 is done when:

```text
- A repo can be created from code
- Files can be committed to that repo
- The latest commit can be verified
- logs/build_log.md is generated and updated
- A fake or real blocker can be detected and explained
- All actions write tool_calls and audit_logs
- Dangerous repo actions are blocked
```

---

# Person 4 - Frontend + Demo + Deployment

## Mission

Person 4 owns what judges see.

They build the dashboard, make the autonomous workflow understandable, manage deployment, and prepare the final demo path. The UI should make MVPilot feel like an AI teammate building a project live, not a hidden backend script.

## Architecture Ownership

Person 4 owns these parts of the loop:

```text
Observe UI
Live progress display
Human approval UI
Report
Deployment
Demo story
```

## Tech Stack

Polished path:

```text
Next.js
TypeScript
Tailwind CSS
Supabase JS client
Supabase Realtime
Vercel
```

Fast fallback:

```text
Streamlit
Supabase Python client
FastAPI calls
```

Use Next.js if the team can move fast. Use Streamlit if deployment or UI time becomes a risk.

## Main Files To Build

Recommended Next.js structure:

```text
frontend/
  app/
    page.tsx
    layout.tsx
  components/
    IdeaInput.tsx
    AgentTimeline.tsx
    RepoStatusPanel.tsx
    RagContextPanel.tsx
    MemoryPanel.tsx
    ToolCallPanel.tsx
    ApprovalPanel.tsx
    BuildLogPanel.tsx
    FinalPackagePanel.tsx
  lib/
    api.ts
    supabase.ts
    types.ts
```

## Required Screens

The MVP can be one dashboard page with these sections:

```text
Idea input
Current run status
Agent timeline
Retrieved docs
Memory used
GitHub repo status
Tool calls
Build log
Blocker and fix panel
Final README/demo/pitch panel
```

## Required User Flow

The judge should be able to:

1. Open the deployed dashboard.
2. Enter or select a messy idea.
3. Click "Start Build".
4. Watch MVPilot create and scope the project.
5. Watch repo/tool/build-log events appear.
6. See retrieved docs and memory.
7. See at least one blocker detection or verification step.
8. Open the generated GitHub repo link.
9. Read the final pitch and demo script.

## Frontend API Calls

Person 4 should call Person 1's backend:

```text
POST /agent/run
POST /agent/approve
GET /agent/tasks/{task_id}
```

The frontend should never call GitHub directly for repo mutation. It should also never use backend-only keys.

## Supabase Realtime Subscriptions

Subscribe to:

```text
tasks
audit_logs
tool_calls
approvals
generated_artifacts
```

The timeline should update when new rows appear.

## UI Event Labels

Use plain labels judges can understand quickly:

```text
Idea received
Docs retrieved
MVP scoped
Repo created
Files generated
Commit verified
Build log updated
Blocker detected
Fix applied
Final README generated
Demo script ready
Pitch ready
```

## Demo Script Ownership

Person 4 owns the final 3-minute explanation.

Recommended structure:

```text
0:00 - Problem: hackathon teams lose time turning broad ideas into real MVPs.
0:20 - Input: paste a messy idea.
0:40 - Observe/Retrieve: MVPilot pulls hackathon and NVIDIA context.
1:05 - Reason: Nemotron scopes a realistic MVP.
1:30 - Act: MVPilot creates the GitHub repo and commits files.
2:00 - Verify: MVPilot checks commits and detects/fixes a blocker.
2:25 - Remember/Report: MVPilot stores memory and generates README, demo script, and pitch.
2:50 - Close: MVPilot is an AI teammate that builds, logs, fixes, and explains the MVP.
```

## Deployment Ownership

Person 4 owns:

```text
- Frontend deployment
- Backend deployment coordination
- Environment variable checklist
- Demo backup plan
- Screenshots or recording if live APIs fail
```

Recommended deployment:

```text
Frontend: Vercel
Backend: Render, Railway, Fly.io, Brev, or DGX Spark
Database: hosted Supabase
```

## Person 4 Deliverables

By integration time, Person 4 must provide:

```text
- Working dashboard
- Start Build flow
- Live timeline
- RAG context display
- Memory display
- GitHub repo status panel
- Tool call and verification display
- Build log view
- Final package view
- Deployed frontend URL
- Demo script
```

## Acceptance Checklist

Person 4 is done when:

```text
- A judge can start the workflow from the UI
- The UI shows live status updates
- The UI shows the generated repo link
- The UI shows retrieved docs and memory
- The UI shows tool calls and verification
- The UI shows the final README/demo/pitch outputs
- The deployed app works on a clean browser session
- There is a backup demo path if live generation fails
```

---

# Shared Contracts

## Shared Task Object

Everyone should use this shape:

```json
{
  "id": "uuid",
  "idea": "Build a healthcare referral coordination agent...",
  "repo_name": "referral-agent-mvp",
  "status": "scoping",
  "scoped_mvp": "One referral workflow that catches missing cardiology documents before submission.",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

## Shared Agent Step Object

```json
{
  "task_id": "uuid",
  "step": "mvp_scoped",
  "message": "Scoped the broad healthcare workflow into one referral coordination MVP.",
  "data": {
    "source_count": 4,
    "model": "llama-3.3-nemotron-super-49b-v1.5"
  }
}
```

## Shared Tool Call Object

```json
{
  "task_id": "uuid",
  "tool_name": "github.create_repo",
  "input_json": {
    "repo_name": "referral-agent-mvp"
  },
  "output_json": {
    "repo_url": "https://github.com/user/referral-agent-mvp"
  },
  "status": "success",
  "verification_status": "verified"
}
```

## Shared Generated Artifact Object

```json
{
  "task_id": "uuid",
  "artifact_type": "demo_script",
  "path": "demo/demo_script.md",
  "content": "Demo script content...",
  "commit_sha": "abc123"
}
```

---

# Build Timeline

## Hours 0-2: Lock The Demo

Everyone works together.

Decide:

```text
- Final demo idea
- Generated repo naming pattern
- Exact UI flow
- API contracts
- Supabase tables
- GitHub account/token strategy
- Fallback mode if live generation is slow
```

Output:

```text
- One written demo path
- One sample messy idea
- One expected generated repo structure
- One shared API contract
```

## Hours 2-6: Build Skeletons In Parallel

Person 1:

```text
- FastAPI app
- State machine skeleton
- Mock Nemotron responses if model setup is not ready
- Calls to stubbed Person 2 and Person 3 functions
```

Person 2:

```text
- Supabase schema
- Seed documents
- Retrieval function
- Audit log helper
```

Person 3:

```text
- GitHub create repo
- Commit files
- Verify commit
- Build log writer
```

Person 4:

```text
- Dashboard shell
- Idea input
- Timeline component
- API client
```

## Hours 6-10: First End-to-End Run

Goal:

```text
One messy idea creates one visible task, one generated repo, one commit, and one timeline.
```

Integration steps:

```text
1. Person 4 calls /agent/run.
2. Person 1 creates task and writes audit log.
3. Person 1 calls Person 2 retrieval.
4. Person 1 scopes MVP with Nemotron or fallback.
5. Person 1 calls Person 3 create_repo and commit_files.
6. Person 3 verifies commit.
7. Person 4 shows every step.
```

## Hours 10-16: Add Winning Features

Add:

```text
- Real RAG snippets in UI
- Persistent memory writeback
- Second-run memory retrieval
- Blocker detection example
- Final README generation
- Demo script generation
- Pitch generation
```

## Hours 16-20: Harden

Fix:

```text
- Broken API contracts
- Missing environment variables
- UI loading states
- Failed GitHub calls
- Empty retrieval results
- Unclear timeline labels
- Deployment bugs
```

Add fallback paths:

```text
- Preseeded generated repo
- Mock GitHub mode
- Static sample retrieved docs
- Cached final pitch
```

## Hours 20-24: Demo Polish

Freeze scope.

Do:

```text
- Deploy frontend
- Deploy backend
- Confirm Supabase works
- Run the demo from a clean browser
- Record backup video or screenshots
- Practice the 3-minute pitch
- Keep a generated repo ready as backup
```

---

# Minimum Demo Feature Set

Do not expand scope until these work:

```text
- Idea input box
- /agent/run backend endpoint
- RAG retrieval from seeded docs
- Nemotron-powered MVP scoping
- GitHub repo creation
- File commit to generated repo
- Build log generation
- Audit timeline in UI
- Commit verification
- Final README generation
- Final demo script generation
- Final pitch generation
```

---

# Recommended Generated Repo Structure

The generated MVP repo should look like:

```text
referral-agent-mvp/
  README.md
  package.json
  frontend/
  backend/
  rag/
  agents/
  data/
    sample_referral.json
    cardiology_policy.md
  logs/
    build_log.md
  demo/
    demo_script.md
    pitch.md
```

This structure gives the judges something concrete to inspect.

---

# Environment Variable Ownership

## Person 1

```text
NVIDIA_API_KEY
NEMOTRON_MODEL
OPENCLAW_API_KEY
AGENT_BACKEND_URL
```

## Person 2

```text
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
EMBEDDING_MODEL
```

## Person 3

```text
GITHUB_TOKEN
GITHUB_OWNER
GITHUB_REPO_PREFIX
SLACK_BOT_TOKEN, optional
SLACK_CHANNEL_ID, optional
```

## Person 4

```text
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
NEXT_PUBLIC_AGENT_BACKEND_URL
```

Security rule:

```text
Frontend only gets NEXT_PUBLIC values and the Supabase anon key.
Service role keys, GitHub tokens, Slack tokens, and NVIDIA keys stay on the backend.
```

---

# Integration Rules

## Rule 1: Use Contracts Before Polish

Agree on request and response shapes before improving UI or prompts.

## Rule 2: Every Action Gets Logged

If MVPilot does something, it should appear in:

```text
audit_logs
tool_calls, if a tool was used
logs/build_log.md, if it matters to the generated repo
```

## Rule 3: Verification Is Required

Every real action needs a check:

```text
Repo created -> fetch repo metadata
Files committed -> fetch commit SHA
Build log written -> fetch file content
Final artifact generated -> store and display it
```

## Rule 4: Fallbacks Are Part Of The Product

If a live API fails, MVPilot should log the failure and use a safe fallback.

Example:

```text
GitHub API failed. MVPilot switched to demo-safe local artifact mode and preserved the planned repo structure.
```

## Rule 5: Keep The Demo Path Narrow

One polished generated MVP beats five incomplete demos.

---

# Final Demo Script Outline

## Opening

```text
Hackathon teams lose hours turning a broad idea into a real MVP. MVPilot acts like an AI teammate that does the first build loop for them.
```

## Live Demo

```text
We enter one messy idea: build a healthcare referral coordination agent.
```

Show:

```text
- MVPilot retrieves hackathon and NVIDIA guidance
- Nemotron scopes the idea into one realistic MVP
- MVPilot creates the GitHub repo
- MVPilot commits the generated structure
- MVPilot logs every step
- MVPilot verifies the commit
- MVPilot detects or explains a blocker
- MVPilot generates README, demo script, and pitch
```

## Closing

```text
MVPilot is not just a planner. It creates the repo, builds the MVP, commits progress, verifies work, stores memory, and produces the final demo package.
```

---

# Final Readiness Checklist

Before submission:

```text
- Frontend is deployed
- Backend is deployed
- Supabase database has seed docs
- GitHub token works
- Generated repo link opens
- Demo path works in a clean browser
- At least one RAG source is visible
- At least one memory item is visible
- At least one verified tool action is visible
- Build log is visible
- Final README is generated
- Demo script is generated
- Pitch is generated
- Backup generated repo exists
- Backup screenshots or recording exist
```

