# Connected GitHub Repo Orchestration Plan

## Summary

Build the real connected-GitHub workflow with a backend-owned OAuth callback. The frontend will no longer receive or submit `github_auth_code`; it will start OAuth through the backend, receive a safe `github_connection_id`, and submit that ID with `POST /agent/run`. The backend workflow will exchange the pending GitHub code, persist the access token encrypted, create a repo in the authenticated user's GitHub account, commit generated files, verify repo health, recover blockers when possible, and produce the final report.

What is missing today:

- Backend OAuth start/callback endpoints.
- Encrypted GitHub token persistence.
- Workflow node for "exchange GitHub code".
- Per-task GitHub token injection into repo/commit/verify tools.
- Frontend replacement of direct GitHub OAuth with backend callback flow.

References:

- GitHub OAuth web flow and token exchange docs: https://docs.github.com/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
- GitHub create repository endpoint and scopes: https://docs.github.com/en/rest/repos/repos#create-a-repository-for-the-authenticated-user

## Key Changes

- Add backend GitHub OAuth endpoints:
  - `GET /github/connect?return_to=<frontend-url>` creates a pending connection, stores a hashed `state`, and redirects to GitHub.
  - `GET /github/callback?code=...&state=...` validates state, stores the GitHub code encrypted, and redirects back to the frontend with `github_connection_id` and `github_status=ready`.
  - Validate `return_to` against configured frontend/CORS origins.
- Add encrypted persistence:
  - New Supabase table `github_connections` with `id`, `task_id`, `state_hash`, encrypted pending code, encrypted access token, scopes, GitHub login/user id, status, return URL, timestamps, and error summary.
  - Add `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_REDIRECT_URI`, `GITHUB_TOKEN_ENCRYPTION_KEY`, and `FRONTEND_BASE_URL` to settings and `.env.example`.
  - Use `cryptography.Fernet`; never log or return raw codes, tokens, or encrypted token blobs.
- Update frontend flow:
  - Remove direct `NEXT_PUBLIC_GITHUB_CLIENT_ID` authorization and `github_auth_code` handling.
  - `Connect GitHub` redirects to `${NEXT_PUBLIC_AGENT_API_URL}/github/connect?return_to=${window.location.origin}`.
  - On return, parse `github_connection_id` and store it in component state/session storage.
  - Submit `github_connection_id` with `POST /agent/run`.
- Update agent workflow:
  - Add `exchange_github_code` node immediately after `receive_idea`.
  - In live mode, fail clearly if `github_connection_id` is missing, invalid, expired, or exchange fails.
  - Exchange code via GitHub, fetch `/user` to verify identity, store encrypted token, clear encrypted code, and attach `github_login`/owner to workflow state.
  - Keep mock mode deterministic and not dependent on GitHub OAuth.
- Update GitHub tool wiring:
  - Let `GitHubConfig` be constructed from a per-task token and owner, not only env vars.
  - Pass that config through `LiveToolAdapter` to `create_repo`, `commit_files`, `verify_commit`, and `check_repo_health`.
  - Create repos via `/user/repos` under the authenticated user account using repo name `mvpilot-generated-{task_id[:8]}`.
  - `verify_build` should check the generated repo health after commit; unrecoverable GitHub auth/permission failures should route to `failed`, not blocker recovery.

## Test Plan

- API/OAuth tests:
  - `/github/connect` redirects to GitHub with expected client id, redirect URI, scope `repo read:user user:email`, and state.
  - `/github/callback` rejects missing/bad state.
  - Valid callback stores encrypted pending code and redirects to frontend with only `github_connection_id`.
  - No response or task detail leaks raw code, token, or encrypted token.
- Workflow tests:
  - Live workflow order includes `receive_idea`, `exchange_github_code`, `retrieve_context`, `scope_mvp`, `plan_repo`, `create_repo`, `generate_files`, `commit_progress`, `verify_build`, final package.
  - Missing GitHub connection in live mode fails with a clear "Connect GitHub" message before repo creation.
  - Successful exchange stores encrypted token, clears pending code, and creates repo using the connected user login.
  - Existing mock workflow tests still pass unchanged.
- GitHub tool tests:
  - `create_repo` and `commit_files` use supplied per-task `GitHubConfig` instead of env `GITHUB_TOKEN`.
  - Repo owner comes from authenticated `/user` login.
  - Private repo creation requires `repo` scope; public repo works with allowed scopes.
- Frontend tests/checks:
  - Connect button uses backend `/github/connect`.
  - Submit payload includes `github_connection_id`, not `github_auth_code`.
  - `npm run lint`, `npm run build`, and full backend `pytest` pass.

## Assumptions

- First version creates repositories only in the connected user's personal account, not organizations.
- Token persistence is encrypted in Supabase with a server-only Fernet key.
- Live repo creation requires a GitHub connection; no env-token fallback.
- GitHub OAuth callback is backend-owned.
- Existing generated artifacts stay small for now; this plan wires real repo creation/commit/health verification, not full app template generation.
