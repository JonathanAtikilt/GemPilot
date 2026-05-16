# Frontend Intake Build Context Implementation Plan

## Summary

Make the frontend intake payload the source of truth for what Person 1 builds. The backend already accepts the frontend fields, but the workflow still mostly reasons from `idea` plus global RAG. This feature normalizes the submitted title, idea, URLs, files, and source marker into a structured intake object, attaches source summaries to build context, and passes that context through `scope_mvp`, `plan_repo`, file generation, README, demo script, and pitch prompts.

This ships before live GitHub repo creation so mock mode can prove the agent builds the right thing first.

## Key Changes

### Intake Contract

- Keep `POST /agent/run` accepting multipart and JSON payloads with `title`, `idea`, `primary_rules_url`, `additional_urls`, `additional_files`, `source`, `github_connected`, and future-compatible `github_connection_id`.
- Add an internal normalized `FrontendIntake` model with `title`, `idea`, `source`, `primaryRulesUrl`, `additionalUrls`, `uploadedFiles`, `githubConnected`, and `githubConnectionId`.
- Persist only safe task metadata in `TaskRecord`; do not expose raw file bytes or OAuth codes in task detail responses.
- Treat `title` as the generated project identity for README title, repo/package naming hints, and final report labels.

### Build Context

- Extend the RAG/build-context layer with a structured `frontendIntake` section and a `sourceContext` section.
- `frontendIntake` contains the normalized submitted fields.
- `sourceContext` contains fetched primary rules URL summary, fetched additional URL summaries, uploaded text-file summaries, unsupported file warnings, fetch/read failure warnings, and source count metadata.
- Use transient per-task source context for v1. Do not write user-submitted URLs/files into persistent global RAG chunks yet.
- Keep the existing `resolvedTechStack` logic unchanged and include it alongside the new intake/source context.

### Source Handling

- Fetch only exact submitted URLs in v1; no recursive crawling.
- Apply timeout, content-type checks, and max-character caps before prompt inclusion.
- URL failures create warnings in `sourceContext`, not whole-run failures.
- Extract text from `.txt`, `.md`, `.json`, and `.csv` uploads.
- For `.pdf`, `.doc`, and `.docx`, persist metadata and emit an unsupported extraction warning in v1.
- Enforce limits before extraction: max 5 uploaded files, max 1 MB per supported text file, max 5 additional URLs, and max 20,000 prompt characters total from source summaries/snippets.

### Workflow

- Update `build_initial_state` and `WorkflowState` to carry `frontend_intake`.
- In `AgentService.run_task_workflow`, build `frontend_intake` from the stored `TaskRecord` and pass it into workflow state.
- In `retrieve_context`, pass intake-derived optional params into `retrieve_build_context`.
- Merge frontend intake and source context into `build_context` before `scope_mvp`.
- Do not make later workflow nodes read raw `retrieved_docs` or raw uploaded content directly; they consume structured `build_context`.

### Prompts And Outputs

- Update prompt builders so `scope_mvp`, `plan_repo`, `file_manifest`, `final_readme`, `demo_script`, and `pitch` receive the structured intake/build context they need.
- Prompt language states that frontend intake is the user's source of truth, source material grounds the build, required RAG rules override user preference, `resolvedTechStack` is binding for architecture/tests/files, and missing or unreadable sources must be surfaced as warnings.
- Update deterministic mock output so generated artifacts reflect the submitted title, submitted idea, source warnings when present, and resolved/default stack.
- Generated README content should no longer default to healthcare wording unless the submitted idea is healthcare-related.

### Documentation

- Keep `connected-github-repo-orchestration-plan.md` separate.
- Implementation order:
  1. Frontend intake build context.
  2. Connected GitHub repo orchestration.

## Test Plan

- API tests cover multipart and JSON frontend payloads, including title, idea, URLs, file metadata, source, GitHub connection status, and safe task detail responses.
- Intake normalization tests cover trimming, blank additional URL removal, future `github_connection_id`, and file/URL limits.
- Source context tests cover successful primary URL summaries, additional URL warnings, supported text uploads, and unsupported-file warnings.
- Build-context tests cover `frontendIntake`, `sourceContext`, and unchanged `resolvedTechStack` behavior.
- Prompt tests cover context inclusion and override language.
- Workflow tests cover non-healthcare intake-driven outputs and source warnings that do not block completion.

## Assumptions And Defaults

- This feature does not create real GitHub repos or exchange OAuth codes. That stays in the connected GitHub orchestration plan.
- v1 uses transient per-task source context, not persistent RAG ingestion, to avoid polluting global RAG with arbitrary user-submitted material.
- PDF/DOC/DOCX text extraction is intentionally deferred until a parser dependency is chosen.
- URL/file read failures should be visible to the agent and final report but should not block mock-mode builds.
- Required hackathon/RAG constraints still beat frontend preferences.
- The default stack remains Next.js, React, TypeScript, Tailwind CSS, Python 3.12, FastAPI, Uvicorn, Supabase Postgres, pgvector, NVIDIA Nemotron, pytest, and `npm run build`.
