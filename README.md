# MVPilot

MVPilot turns a messy MVP idea into a GitHub repository through a backend-owned
GitHub OAuth session, a Nemotron/OpenClaw orchestration pipeline, and visible
agent build logs in the website.

## Local Setup

1. Copy environment variables:

```bash
cp .env.example .env
```

2. Create a GitHub OAuth App at <https://github.com/settings/developers>.

- Homepage URL: `http://localhost:3000`
- Authorization callback URL: `http://127.0.0.1:3001/api/auth/github/callback`
- Required scope is requested by the backend: `repo read:user user:email`

3. Fill these backend values in `.env`:

```bash
GITHUB_OAUTH_CLIENT_ID=...
GITHUB_OAUTH_CLIENT_SECRET=...
GITHUB_OAUTH_REDIRECT_URI=http://127.0.0.1:3001/api/auth/github/callback
GITHUB_TOKEN_ENCRYPTION_KEY=...
FRONTEND_BASE_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:3001
```

Generate the encryption key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For live model/repo execution, also set:

```bash
ADAPTER_MODE=live
MOCK_MODE=false
MVPILOT_MOCK_TOOLS=false
NVIDIA_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```

## Run Locally

Backend:

```bash
.venv/bin/uvicorn agent.main:app --host 127.0.0.1 --port 3001 --reload
```

Frontend:

```bash
cd frontend
npm install
NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:3001 npm run dev
```

Open <http://localhost:3000>, connect GitHub, enter the MVP idea, choose repo
settings, launch the build, and watch the agent activity log.

## Current Flow

- The frontend sends users to the backend GitHub OAuth route.
- The backend validates OAuth state, exchanges the code with GitHub, fetches the
  authenticated GitHub user, encrypts the token, and stores only a connection id
  in the browser.
- The orchestrator uses that connection id to create a new repo under the
  authenticated user, generate frontend/backend/database/test/docs files, commit
  them through the GitHub API, verify repo health, and expose repo links.
- The UI polls task telemetry and shows GitHub connection, repo creation, plan
  generation, file generation, commit, verification, and final landing events.

## Tests

```bash
pytest
cd frontend && npm run lint
```

Main project docs live in `docs/`.

- `docs/MVPilot_README.md` - project overview and pitch
- `docs/final-team-split.md` - detailed hackathon member plan (Nemotron/Brev track)
- `docs/tech-stack.md` - suggested stack
- `docs/enterprise_agent_architecture_template.md` - enterprise agent loop template
- `docs/hackathon_team_split_plan.md` - earlier team split reference
