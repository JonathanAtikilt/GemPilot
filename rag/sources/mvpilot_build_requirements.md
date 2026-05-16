# MVPilot Build Requirements

Authoritative build constraints for the Orchestrator, GitHub Agent, and demo workflow.

# Required Deliverables

- Working MVP that demonstrates the core agent workflow end to end
- GitHub repository with visible commit history
- README.md with problem statement, setup, and run instructions
- Setup instructions that a judge can follow locally
- Agent activity/build log showing orchestration and tool use
- Demo-ready workflow the frontend can display live
- Clear NVIDIA/Nemotron usage explanation in README or docs

# Allowed Tools and APIs

- NVIDIA API for Nemotron reasoning, embeddings, and reranking
- GitHub API for repo, branch, commit, and PR actions
- Supabase for Postgres, pgvector, logs, and project state
- FastAPI for backend endpoints
- React or Next.js for frontend UI
- Cursor/Codex only as development assistants, not as hidden runtime dependencies unless explicitly configured
- Environment variables for secrets; never commit API keys

# Required Repository Format

- README.md at repository root
- .env.example with documented variables and no real secrets
- docs/BUILD_LOG.md for agent/build narrative
- docs/ARCHITECTURE.md describing agents and data flow
- frontend or apps/web folder for UI code
- backend or apps/api folder for API code
- rag/sources folder for indexed knowledge
- logs folder for runtime build output
- clear install/run instructions in README
- no committed secrets or service-role keys

# Required Demo Format

- User enters a project idea in the UI
- Orchestrator calls RAG for build context before planning
- RAG returns rules, deliverables, tech stack, and evidence
- Orchestrator generates an implementation plan from grounded context
- GitHub Agent creates or connects a repository
- GitHub Agent writes files and commits incremental changes
- Frontend shows live agent progress and log updates
- Final repo or PR link is displayed to the user
- Demo clearly explains NVIDIA/Nemotron usage in the workflow

# Required Tech Stack Pieces

- Frontend UI: React or Next.js
- Backend API: FastAPI
- Database: Supabase Postgres
- Vector search: Supabase pgvector
- Embeddings: NVIDIA llama-nemotron-embed-1b-v2
- Reranking: NVIDIA llama-nemotron-rerank-1b-v2
- Orchestrator reasoning: Nemotron reasoning model
- GitHub integration: GitHub API or Octokit
- Secrets: backend-only environment variables

# Scope Warnings

- Do not add recursive web crawling for MVP
- Do not let the RAG Agent directly commit files to GitHub
- Do not expose SUPABASE_SERVICE_ROLE_KEY to the frontend
- Do not build full deployment automation before repo generation works
- Do not treat raw logs as higher authority than hackathon rules or official model docs
