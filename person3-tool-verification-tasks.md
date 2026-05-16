# Person 3 Tool + Verification Task Tracker

This file is the implementation checklist for Person 3. Use it to keep the GitHub/tool layer small, testable, and hard to break during integration.

Person 3 owns:

```text
Act
Verify
Tool safety
GitHub execution
Blocker detection
```

The goal is not to build every possible integration. The goal is to make a narrow set of live actions work reliably and prove each action succeeded.

## Bug Prevention Rules

- Do one task at a time.
- Test each tool before connecting it to Person 1's state machine.
- Every live action must have a verification step.
- Every tool must return a predictable dict shape.
- Never let demo tools modify the `MVPilot` source repo.
- Only create or update repos whose names start with `mvpilot-generated-`.
- Refuse destructive actions such as delete repo, force push, rewrite history, or secret changes.
- Keep a mock mode so the demo still works if GitHub credentials or network calls fail.

## Shared Result Shape

All Person 3 tools should return something close to:

```json
{
  "tool_name": "github.create_repo",
  "status": "success",
  "output": {},
  "verification_status": "verified",
  "error": null
}
```

## Environment Variables

Required for live GitHub mode:

```text
GITHUB_TOKEN
GITHUB_OWNER
GITHUB_REPO_PREFIX=mvpilot-generated-
```

Optional:

```text
MVPILOT_MOCK_TOOLS=true
SLACK_BOT_TOKEN
SLACK_CHANNEL_ID
```

---

## Task 1: Define Tool Schemas

Create:

```text
tools/schemas.py
```

Define shared request/result shapes:

```text
ToolResult
CreateRepoRequest
CommitFilesRequest
FilePayload
VerificationResult
RepoHealthResult
BlockerResult
```

Acceptance criteria:

- [x] Tool inputs are validated before API calls.
- [x] Tool outputs use the shared result shape.
- [x] Invalid file payloads fail clearly.
- [x] Fake inputs can be tested without GitHub credentials.

Bug-prevention checks:

- [x] Missing `path` or `content` in a file payload returns a validation error.
- [x] Tool failures preserve the original error message in `error`.

---

## Task 2: Add Safety Policy

Create:

```text
tools/policy.py
```

Implement rules for:

```text
Allowed:
  create generated repos
  commit generated files
  read repo data
  verify commits

Blocked:
  delete repos
  force push
  rewrite history
  modify unrelated repos
  change secrets
```

Acceptance criteria:

- [x] Repo names must start with `mvpilot-generated-`.
- [x] Dangerous actions return a refused result.
- [x] Policy can be called before every GitHub mutation.

Bug-prevention checks:

- [x] `MVPilot` and other non-generated repo names are rejected.
- [x] Empty repo names are rejected.
- [x] Path traversal attempts such as `../secret` are rejected.

---

## Task 3: Implement GitHub Client Setup

Create or update:

```text
tools/github_tool.py
```

Read:

```text
GITHUB_TOKEN
GITHUB_OWNER
GITHUB_REPO_PREFIX
MVPILOT_MOCK_TOOLS
```

Acceptance criteria:

- [x] GitHub requests use authenticated headers.
- [x] Missing credentials produce a clear error or mock result.
- [x] API helper centralizes timeout, status handling, and JSON parsing.

Bug-prevention checks:

- [x] Token is never printed or returned.
- [x] HTTP errors include status code and safe response summary.
- [x] Mock mode does not call GitHub.

---

## Task 4: Create Repo Tool

Implement:

```python
create_repo(repo_name: str, description: str, visibility: str) -> dict
```

The tool should:

```text
validate repo name with policy
create repo through GitHub API
return repo_name, repo_url, and status
verify repo exists by fetching metadata
```

Acceptance criteria:

- [x] A repo can be created from code.
- [x] The returned `repo_url` opens the generated repo.
- [x] Existing repo conflicts return a useful failure.
- [x] Repo creation is verified by reading repo metadata.

Bug-prevention checks:

- [x] Non-generated repo names are refused.
- [x] Invalid visibility values are rejected.
- [x] Create failure does not continue to commit files.

---

## Task 5: Commit Files Tool

Implement:

```python
commit_files(repo_name: str, files: list[dict], message: str) -> dict
```

Input file shape:

```json
{
  "path": "README.md",
  "content": "# Referral Agent MVP"
}
```

Acceptance criteria:

- [x] Multiple files can be committed in one logical operation.
- [x] The tool returns `commit_sha`, `message`, `files_changed`, and `status`.
- [x] File paths are validated before commit.
- [x] The commit is verified after creation.

Bug-prevention checks:

- [x] Empty file list is rejected.
- [x] Empty commit message is rejected.
- [x] Attempts to write outside the repo are rejected.
- [x] Binary or oversized content is handled explicitly or rejected.

---

## Task 6: Verify Commit Tool

Create or update:

```text
tools/verifier.py
```

Implement:

```python
verify_commit(repo_name: str, commit_sha: str) -> dict
```

The tool should:

```text
fetch the commit from GitHub
confirm the SHA exists
return changed files
return verified true or false
```

Acceptance criteria:

- [x] Real commit SHAs verify successfully.
- [x] Fake commit SHAs fail clearly.
- [x] Changed files are returned.
- [x] Verification failures do not crash the agent.

Bug-prevention checks:

- [x] Empty SHA is rejected.
- [x] Verification checks the intended generated repo.
- [x] GitHub API failure returns `verification_status: failed`.

---

## Task 7: Build Log Writer

Create:

```text
tools/repo_writer.py
```

Implement:

```python
append_build_log(task_id: str, repo_name: str, message: str, data: dict) -> dict
```

It should update:

```text
logs/build_log.md
```

Acceptance criteria:

- [x] First log call creates `logs/build_log.md`.
- [x] Later log calls append without deleting previous entries.
- [x] Log entries include timestamp, task ID, message, and useful metadata.
- [x] Updated build log content is verified by reading the file back.

Bug-prevention checks:

- [x] Empty messages are rejected.
- [x] Append conflicts are retried once or fail clearly.
- [x] Build log writes use the same repo safety policy.

---

## Task 8: Repo Health Checker

Create:

```text
tools/build_checker.py
```

Implement:

```python
check_repo_health(repo_name: str) -> dict
```

Minimum checks:

```text
README.md exists
logs/build_log.md exists
demo/demo_script.md exists
package.json or requirements.txt exists
src/ or backend/ exists
at least one commit exists after scaffold
```

Acceptance criteria:

- [x] Healthy generated repos pass.
- [x] Incomplete repos return a list of missing files or folders.
- [x] Health result can be shown directly in the frontend.

Bug-prevention checks:

- [x] Missing repo returns a clear failure.
- [x] Checks do not mutate the repo.
- [x] A partial failure still reports all checks that could run.

---

## Task 9: Blocker Detector

Create:

```text
tools/blocker_detector.py
```

Implement:

```python
detect_blocker(logs: list[dict]) -> dict
```

Start with simple known patterns:

```text
route_mismatch
missing_dependency
build_failed
missing_env_var
github_api_failure
```

Example result:

```json
{
  "has_blocker": true,
  "blocker_type": "route_mismatch",
  "summary": "Frontend called /api/analyze but backend exposes /api/analyze-referral.",
  "recommended_fix": "Update frontend fetch call to /api/analyze-referral."
}
```

Acceptance criteria:

- [x] Fake route mismatch logs produce a route mismatch blocker.
- [x] Missing dependency logs produce a missing dependency blocker.
- [x] Clean logs return `has_blocker: false`.
- [x] Every blocker includes a recommended fix.

Bug-prevention checks:

- [x] Empty log list is handled.
- [x] Unknown errors produce a generic blocker instead of crashing.
- [x] Detector does not depend on live GitHub access.

---

## Task 10: Tool Call Logger

Create:

```text
tools/tool_logger.py
```

Write every action to Supabase when available:

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

Acceptance criteria:

- [x] Successful tool calls are logged.
- [x] Failed tool calls are logged.
- [x] Verification status is included.
- [x] Logger degrades gracefully if Supabase is unavailable.

Bug-prevention checks:

- [x] Secrets are redacted before logging.
- [x] Logger failures do not hide the original tool result.
- [x] `task_id` is included whenever available.

---

## Task 11: Mock Mode

Add fallback behavior when GitHub credentials are missing or API calls fail.

Use:

```text
MVPILOT_MOCK_TOOLS=true
```

Acceptance criteria:

- [x] Full Person 3 flow can run without a GitHub token.
- [x] Mock results use the same result shape as live results.
- [x] Mock mode clearly marks outputs as mock/demo-safe.
- [x] Person 1 can integrate against mock and live modes without code changes.

Bug-prevention checks:

- [x] Mock mode does not pretend verification is live.
- [x] Mock commit SHAs are obviously synthetic.
- [x] Switching mock mode off requires real credentials.

---

## Task 12: End-To-End Person 3 Smoke Test

Create:

```text
scripts/test_person3_flow.py
```

It should run:

```text
create_repo
commit_files
append_build_log
verify_commit
check_repo_health
detect_blocker
```

Acceptance criteria:

- [x] One command runs the Person 3 happy path.
- [x] The script supports mock mode.
- [x] The script prints the generated repo URL or mock repo URL.
- [x] The script exits non-zero when a required live step fails.

Bug-prevention checks:

- [x] The script uses a unique generated repo name.
- [x] It does not touch the `MVPilot` source repo.
- [x] It validates that verification happens after each live action.

---

## Integration Checklist With Person 1

Person 1 needs these callable functions:

```python
create_repo(repo_name: str, description: str, visibility: str) -> dict
commit_files(repo_name: str, files: list[dict], message: str) -> dict
check_repo_health(repo_name: str) -> dict
detect_blocker(logs: list[dict]) -> dict
verify_commit(repo_name: str, commit_sha: str) -> dict
```

Before integration:

- [x] Function names and signatures match Person 1's contract.
- [x] Return shapes are stable.
- [x] Mock mode works.
- [x] Live GitHub mode has been tested once.
- [x] Dangerous actions are blocked.
- [x] Every action logs or returns verification status.

## Done Definition

Person 3 is done when:

- [x] A repo can be created from code.
- [x] Files can be committed to that repo.
- [x] The latest commit can be verified.
- [x] `logs/build_log.md` is generated and updated.
- [x] Repo health checks return useful pass/fail details.
- [x] A fake or real blocker can be detected and explained.
- [ ] All actions can write `tool_calls` and `audit_logs` when logging is available.
- [x] Dangerous repo actions are blocked.
- [x] The whole layer works in mock mode.
