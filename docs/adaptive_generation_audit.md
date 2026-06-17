# GemPilot Adaptive Generation Audit

This document maps where GemPilot enforces a predetermined full-stack web template (React + Vite + FastAPI + Postgres + auth + dashboard) and how each layer should change.

## Pipeline flow

```
idea → scope_mvp → recommend_stack → plan_repo → generate_files → ensure_imports_resolve → validate_mvp → commit_repo
```

Template pressure is highest on **degraded/mock paths**, **hydrate/merge scaffold**, **prompts**, **requirements enrichment**, and **validation**.

---

## File-by-file audit

| File | Responsibility | Forces template? | Proposed fix |
|------|----------------|------------------|--------------|
| `agent/generated_project.py` | Canonical `build_project_artifacts()` factory | **Yes** — web default emits `src/App.jsx`, `backend/main.py`, auth routes, dashboard UI | Branch on `ProjectProfile`; emit paths from `ArchitecturePlanner` |
| `agent/project_generation.py` | Priority paths, merge/hydrate, `ensure_imports_resolve` | **Yes** — `_WEB_PRIORITY_PATHS`, scaffold overwrites model on priority paths | Gap-fill docs/demo only; derive paths from architecture plan |
| `agent/project_validation.py` | `validate_project_output()` — 20+ checks | **Yes** — requires `src/lib/api.js`, seed script, dashboard semantics, StudyPilot benchmark | Split by `ProjectProfile`; use `adaptive_validation.py` |
| `agent/mvp_validation.py` | Thin alias to `validate_project_output` | **Inherited** | Delegate to adaptive validator |
| `agent/workflow.py` | LangGraph nodes, stack defaults, fallback to `hydrate_file_manifest` | **Yes** — defaults React/FastAPI/Postgres; template fallback | Use classifier + planner; no hardcoded stack defaults |
| `agent/model_client.py` | Degraded/mock payloads | **Yes** — `_repo_plan_payload` hardcodes 34-path tree | Derive plan from `ArchitecturePlanner` |
| `agent/idea_aware_partial.py` | Partial degraded client | **Yes** — calls `build_project_artifacts` | Minimal idea-specific subset only |
| `agent/project_depth.py` | `enrich_project_requirements` | **Yes** — injects `GET /api/dashboard`, dashboard tabs/flows | Skip API/dashboard defaults for non-web profiles |
| `agent/prompts.py` | Staged generation prompts | **Yes** — FastAPI/React file layouts in db/backend/frontend stages | Parameterize from `recommended_stack` + profile |
| `agent/code_generator.py` | 5 fixed stages (db→backend→frontend→docs→demo) | **Yes** — always runs all stages | Skip stages based on profile |
| `agent/stack_recommendation.py` | Heuristic stack | **Partial** — web → Next.js + FastAPI + Postgres | Honor profile before web defaults |
| `agent/orchestrator.py` | Plan composition | **No** — pass-through | Attach `project_profile` to plan |
| `agent/orchestration_pipeline.py` | Phase metadata | **No** | — |
| `tools/github_tool.py` | Git export | **No** | — |
| `tools/repo_writer.py` | Build log append | **No** | — |

---

## Critical enforcement points (priority order)

1. **`merge_scaffold_over_model` / `hydrate_file_manifest`** — scaffold wins on priority paths → gap-fill only.
2. **`build_project_artifacts`** — always emits Vite+FastAPI for `web app` → profile-driven emission.
3. **`model_client._repo_plan_payload`** — static 34-file tree → planner-driven tree.
4. **`validate_project_output`** — template law for all projects → profile-aware checks.
5. **`prompts.py` staged generators** — fixed FastAPI/React paths → conditional stages.
6. **`project_depth.enrich_project_requirements`** — universal dashboard routes → archetype-aware.

---

## New modules (this refactor)

| Module | Role |
|--------|------|
| `agent/project_classifier.py` | Classify idea → category, architecture type, layer requirements |
| `agent/architecture_planner.py` | Dynamic `file_tree`, implementation stages, validation profile |
| `agent/adaptive_validation.py` | Project-aware validation (imports, runtime, workflows) |

---

## Target flow

```
User idea
  → ProjectClassifier (category + layer requirements)
  → ArchitecturePlanner (dynamic file tree + stages)
  → LLM implementation (stages filtered by profile)
  → ensure_imports_resolve (repair only, no template overwrite)
  → adaptive validation (profile-aware)
  → GitHub export
```
