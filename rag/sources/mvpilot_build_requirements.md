# GemPilot Build Requirements

Authoritative build constraints for the Orchestrator, GitHub Agent, and demo workflow.

# Required Deliverables

- Complete hackathon-ready full-stack project that demonstrates the submitted product workflow end to end
- GitHub repository with visible commit history
- README.md with problem statement, setup, and run instructions
- Frontend app with polished project-specific UI
- Backend API with real product routes
- Database schema/models with seed/sample data
- Authentication when relevant to the product
- Tests for generated backend/API behavior
- API docs and deployment instructions
- `.env.example` with safe placeholders only
- Setup instructions that a judge can follow locally
- Agent activity/build log showing orchestration and tool use
- Demo-ready workflow the frontend can display live
- Repository demo materials: `demo/script.md`, `demo/storyboard.md`, `demo/demo_walkthrough.md`, `demo/video_outline.md`, and optional `demo/voiceover.md`
- Hackathon submission summary in `docs/HACKATHON_SUBMISSION.md`
- Clear Google AI/Gemini usage explanation in README or docs

# Allowed Tools and APIs

- Google AI API for Gemini reasoning, embeddings, and reranking
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
- docs/API_SPEC.md documenting backend routes
- docs/DATABASE_SCHEMA.sql or equivalent database/schema document
- docs/DEPLOY.md with deployment instructions
- docs/HACKATHON_SUBMISSION.md with judging summary
- demo folder with project-specific video materials
- data/seed.json or seed script for sample data
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
- Final repo includes demo video materials specific to the generated project
- Demo clearly explains Google AI/Gemini usage in the workflow

# Required Tech Stack Pieces

- Frontend UI: React or Next.js
- Backend API: FastAPI
- Database: Supabase Postgres
- Vector search: Supabase pgvector
- Embeddings: Google AI gemini-embedding-001
- Reranking: Google AI cosine similarity ranking
- Orchestrator reasoning: Gemini reasoning model
- GitHub integration: GitHub API or Octokit
- Secrets: backend-only environment variables

# Security Constraints

- Frontend must never send or store GitHub, Google AI, or Supabase service-role tokens
- GitHub OAuth callback must exchange the code server-side
- Supabase service-role key is backend-only and must not be referenced in Next.js client code
- Generated repositories may include `.env.example` placeholders but must never commit `.env`
- Audit logs and build logs should summarize tool calls without secret values

# Agent Boundaries

- Frontend collects launch intent and displays progress; it does not decide project scope
- Orchestrator calls RAG before planning and owns the final implementation plan
- RAG retrieves, summarizes, and cites context; it does not choose or commit the project
- GitHub Agent creates or updates repositories using server-side credentials only
- Black Box stores decisions, logs, artifacts, errors, and final landing summaries

# Scope Warnings

- Do not add recursive web crawling before complete project generation works
- Do not let the RAG Agent directly commit files to GitHub
- Do not expose SUPABASE_SERVICE_ROLE_KEY to the frontend
- Do not build full deployment automation before complete repo generation works
- Do not treat raw logs as higher authority than hackathon rules or official model docs
