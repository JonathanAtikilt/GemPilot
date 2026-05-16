from __future__ import annotations

import asyncio
import operator
import json
from datetime import UTC, datetime
from typing import Annotated, Any, Awaitable, Callable, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.config import Settings
from agent.model_client import (
    DeterministicModelClient,
    ModelCallResult,
    ModelClient,
    NemotronModelClient,
)
from agent.model_outputs import (
    BlockerAnalysisOutput,
    DemoScriptOutput,
    FilePlanOutput,
    FileManifestOutput,
    FinalReadmeOutput,
    GeneratedFileOutput,
    MvpScopeOutput,
    PitchOutput,
    RepoPlanOutput,
)
from agent.prompts import (
    build_blocker_analysis_prompt,
    build_demo_script_prompt,
    build_file_content_prompt,
    build_file_plan_prompt,
    build_file_manifest_prompt,
    build_final_readme_prompt,
    build_pitch_prompt,
    build_plan_repo_prompt,
    build_scope_mvp_prompt,
)
from agent.schemas import AgentStep
from agent.adapters import AuditAdapter, RagMemoryAdapter, ToolAdapter, InMemoryAuditAdapter, InMemoryToolAdapter
from agent.frontend_intake import (
    FrontendIntake,
    build_optional_params_from_frontend_intake,
    build_source_context,
)
from agent.generated_project import merge_with_project_artifacts, title_from_idea
from agent.github_oauth import GitHubConnectionService, GitHubOAuthError
from agent.live_adapters import LiveRagMemoryAdapter
from tools.build_checker import merge_repo_health_scaffold
from agent.openclaw_runtime import (
    registered_tools_for_settings,
    runtime_name_for_settings,
)
from agent.schemas import UploadedSourceFileContent

ListReducer = Annotated[list[dict[str, Any]], operator.add]
StepReducer = Annotated[list[AgentStep], operator.add]

NODE_FLIGHT_STAGE: dict[str, str] = {
    "receive_idea": "preflight",
    "exchange_github_code": "preflight",
    "retrieve_context": "radar_scan",
    "scope_mvp": "flight_plan",
    "plan_repo": "flight_plan",
    "create_repo": "autopilot",
    "generate_files": "autopilot",
    "debug_generated_files": "autopilot",
    "commit_progress": "autopilot",
    "verify_build": "autopilot",
    "handle_blocker": "autopilot",
    "generate_final_package": "black_box",
    "remember_outcome": "black_box",
    "report_result": "landed",
    "failed": "failed",
}

NODE_AGENT: dict[str, str] = {
    "receive_idea": "orchestrator",
    "exchange_github_code": "github",
    "retrieve_context": "rag",
    "scope_mvp": "orchestrator",
    "plan_repo": "orchestrator",
    "create_repo": "github",
    "generate_files": "orchestrator",
    "debug_generated_files": "orchestrator",
    "commit_progress": "github",
    "verify_build": "github",
    "handle_blocker": "orchestrator",
    "generate_final_package": "orchestrator",
    "remember_outcome": "black_box",
    "report_result": "orchestrator",
    "failed": "orchestrator",
}


class WorkflowState(TypedDict):
    task_id: str
    idea: str
    repo_visibility: Literal["public", "private"]
    demo_mode: bool
    source_urls: NotRequired[list[str]]
    runtime: str
    registered_tools: NotRequired[list[str]]
    openclaw_trace: ListReducer
    status: str
    nemotron_model: str
    mock_mode: bool
    blocker_recovered: bool
    agent_steps: StepReducer
    graph_trace: StepReducer
    retrieved_docs: ListReducer
    build_context: NotRequired[dict[str, Any]]
    frontend_intake: NotRequired[dict[str, Any]]
    uploaded_file_contents: NotRequired[list[dict[str, Any]]]
    memory_matches: ListReducer
    tool_calls: ListReducer
    generated_artifacts: ListReducer
    last_tool_result: NotRequired[dict[str, Any]]
    repo: NotRequired[dict[str, Any]]
    github_connection: NotRequired[dict[str, Any]]
    mvp_scope: NotRequired[dict[str, Any]]
    repo_plan: NotRequired[dict[str, Any]]
    file_manifest: NotRequired[dict[str, Any]]
    blocker_analysis: NotRequired[dict[str, Any]]
    final_readme: NotRequired[dict[str, Any]]
    demo_script: NotRequired[dict[str, Any]]
    pitch: NotRequired[dict[str, Any]]
    final_report: NotRequired[dict[str, Any] | None]
    failure_reason: NotRequired[str | None]



def build_initial_state(
    *,
    task_id: str,
    idea: str,
    repo_visibility: Literal["public", "private"],
    demo_mode: bool,
    settings: Settings,
    source_urls: list[str] | None = None,
    frontend_intake: dict[str, Any] | None = None,
    uploaded_file_contents: list[dict[str, Any]] | None = None,
) -> WorkflowState:
    normalized_intake = frontend_intake or FrontendIntake(idea=idea).model_dump()
    return {
        "task_id": task_id,
        "idea": idea,
        "repo_visibility": repo_visibility,
        "demo_mode": demo_mode,
        "source_urls": list(source_urls or []),
        "runtime": runtime_name_for_settings(settings),
        "registered_tools": registered_tools_for_settings(settings),
        "openclaw_trace": [],
        "status": "started",
        "nemotron_model": settings.nemotron_model,
        "mock_mode": settings.mock_mode,
        "blocker_recovered": False,
        "agent_steps": [],
        "graph_trace": [],
        "retrieved_docs": [],
        "build_context": {},
        "frontend_intake": normalized_intake,
        "uploaded_file_contents": uploaded_file_contents or [],
        "memory_matches": [],
        "tool_calls": [],
        "generated_artifacts": [],
        "final_report": None,
        "failure_reason": None,
    }


def build_workflow(
    settings: Settings,
    *,
    model_client: ModelClient | None = None,
    audit: AuditAdapter | None = None,
    retrieval: RagMemoryAdapter | None = None,
    tools: ToolAdapter | None = None,
    github_connections: GitHubConnectionService | None = None,
    progress_callback: Callable[[str, list[AgentStep]], Awaitable[None]] | None = None,
):
    active_audit = audit or InMemoryAuditAdapter(model_name=settings.nemotron_fast_model)
    active_model_client = model_client or _build_default_model_client(settings)
    active_retrieval = retrieval or LiveRagMemoryAdapter()
    active_tools = tools or InMemoryToolAdapter()

    def append_step(
        *,
        state: WorkflowState | None = None,
        node_name: str,
        message: str,
        decision_trace: list[str],
        status: str = "completed",
    ) -> dict[str, list[AgentStep]]:
        project_id = state["task_id"] if state else None
        flight_stage = NODE_FLIGHT_STAGE.get(node_name)
        agent = NODE_AGENT.get(node_name)
        step = active_audit.write_audit_log(
            node_name=node_name,
            message=message,
            decision_trace=decision_trace,
            status=status,
            project_id=project_id,
            flight_stage=flight_stage,
            agent=agent,
        )
        return {"agent_steps": [step], "graph_trace": [step]}

    def append_model_step(
        *,
        state: WorkflowState | None = None,
        node_name: str,
        message: str,
        result: ModelCallResult,
        status: str = "completed",
        prompt_purpose: str | None = None,
        extra_trace: list[str] | None = None,
    ) -> dict[str, list[AgentStep]]:
        step = build_model_step(
            state=state,
            node_name=node_name,
            message=message,
            result=result,
            status=status,
            prompt_purpose=prompt_purpose,
            extra_trace=extra_trace,
        )
        return {"agent_steps": [step], "graph_trace": [step]}

    def build_model_step(
        *,
        state: WorkflowState | None = None,
        node_name: str,
        message: str,
        result: ModelCallResult,
        status: str = "completed",
        prompt_purpose: str | None = None,
        extra_trace: list[str] | None = None,
    ) -> AgentStep:
        return AgentStep(
            project_id=state["task_id"] if state else None,
            flight_stage=NODE_FLIGHT_STAGE.get(node_name),
            agent=NODE_AGENT.get(node_name),
            node_name=node_name,
            status=status,
            message=message,
            model=result.model,
            prompt_purpose=prompt_purpose or result.purpose,
            model_mode=result.mode,
            decision_trace=[
                *result.output.decision_trace,
                *(extra_trace or []),
            ],
            timestamp=datetime.now(UTC),
        )

    async def publish_progress(state: WorkflowState, step: AgentStep) -> None:
        if progress_callback is not None:
            await progress_callback(state["task_id"], [step])

    def receive_idea(state: WorkflowState) -> dict[str, Any]:
        return append_step(
            state=state,
            node_name="receive_idea",
            message="Received the idea and initialized the Person 1 workflow.",
            decision_trace=[
                "Accepted the trimmed idea payload.",
                "Kept endpoint response shape unchanged.",
                f"Demo mode is {state['demo_mode']}.",
            ],
        )

    async def exchange_github_code(state: WorkflowState) -> dict[str, Any]:
        frontend_intake = FrontendIntake.model_validate(
            state.get("frontend_intake") or {"idea": state["idea"]}
        )
        connection_id = frontend_intake.githubConnectionId

        if settings.mock_mode:
            return {
                **append_step(
                    state=state,
                    node_name="exchange_github_code",
                    message="Mock mode skipped live GitHub OAuth exchange.",
                    decision_trace=[
                        "Mock mode keeps the workflow deterministic.",
                        "No GitHub code or token is required for mock repository actions.",
                    ],
                ),
                "github_connection": {
                    "status": "mock_skipped",
                    "connection_id": connection_id,
                    "login": None,
                },
            }

        if not connection_id:
            reason = (
                "GitHub is not connected. Use Connect GitHub on the website before launching "
                "so the backend receives a github_connection_id."
            )
            return {
                **append_step(
                    state=state,
                    node_name="exchange_github_code",
                    status="failed",
                    message=reason,
                    decision_trace=[
                        "Live mode requires a backend-issued github_connection_id.",
                        "Stopped before RAG planning because repo actions need an authenticated user.",
                    ],
                ),
                "status": "failed",
                "failure_reason": reason,
                "github_connection": {
                    "status": "missing",
                    "connection_id": None,
                    "login": None,
                },
            }

        if github_connections is None:
            reason = "GitHub connection service is not configured."
            return {
                **append_step(
                    state=state,
                    node_name="exchange_github_code",
                    status="failed",
                    message=reason,
                    decision_trace=[
                        "Live mode cannot exchange a GitHub connection without the service.",
                        "Stopped before repo creation.",
                    ],
                ),
                "status": "failed",
                "failure_reason": reason,
            }

        try:
            auth = await github_connections.exchange_for_workflow(
                connection_id,
                task_id=state["task_id"],
            )
            configure_github = getattr(active_tools, "set_github_config", None)
            if configure_github is None:
                raise GitHubOAuthError("GitHub tool adapter cannot accept per-task credentials.")
            configure_github(auth.config)
        except GitHubOAuthError as exc:
            reason = str(exc) or "GitHub OAuth exchange failed."
            return {
                **append_step(
                    state=state,
                    node_name="exchange_github_code",
                    status="failed",
                    message=reason,
                    decision_trace=[
                        "GitHub OAuth exchange did not complete.",
                        "No repository action was attempted.",
                    ],
                ),
                "status": "failed",
                "failure_reason": reason,
            }

        return {
            **append_step(
                state=state,
                node_name="exchange_github_code",
                message="Exchanged the backend GitHub connection for live repo credentials.",
                decision_trace=[
                    "Validated the backend-issued github_connection_id.",
                    f"Configured GitHub tools for connected user {auth.login}.",
                    "Kept the access token out of workflow state and API responses.",
                ],
            ),
            "github_connection": {
                "status": "exchanged",
                "connection_id": auth.connection_id,
                "login": auth.login,
                "scopes": auth.scopes,
            },
        }

    async def retrieve_context(state: WorkflowState) -> dict[str, Any]:
        frontend_intake = FrontendIntake.model_validate(
            state.get("frontend_intake") or {"idea": state["idea"]}
        )
        source_urls = list(state.get("source_urls") or [])
        index_summary: dict[str, Any] = {
            "documentsLoaded": 0,
            "chunksCreated": 0,
        }
        if source_urls:
            index_summary = await active_retrieval.index_source_urls(source_urls)

        optional_params = build_optional_params_from_frontend_intake(frontend_intake) or {}
        if source_urls:
            optional_params = {**optional_params, "sourceUrls": source_urls}
        optional_params = optional_params or None

        build_context = await active_retrieval.retrieve_build_context(
            state["task_id"],
            state["idea"],
            optional_params=optional_params,
            rules_url=frontend_intake.primaryRulesUrl,
            reference_urls=frontend_intake.additionalUrls,
            context_needed=[
                "required_deliverables",
                "allowed_tools_apis",
                "required_repository_format",
                "required_demo_format",
                "required_tech_stack_pieces",
                "hackathon_rules",
                "nvidia_model_usage",
                "security_constraints",
                "agent_boundaries",
                "scope_warnings",
            ],
            top_k=8,
        )
        uploaded_files = [
            UploadedSourceFileContent.model_validate(file)
            for file in state.get("uploaded_file_contents", [])
        ]
        source_context = await build_source_context(
            frontend_intake,
            uploaded_files=uploaded_files,
        )
        build_context = {
            **build_context,
            "frontendIntake": frontend_intake.model_dump(),
            "sourceContext": source_context,
        }
        docs = (
            await active_retrieval.retrieve_hackathon_context(state["idea"])
            + await active_retrieval.retrieve_nvidia_context(state["idea"])
        )
        memories = await active_retrieval.find_similar_builds(state["idea"])

        evidence_count = len(build_context.get("evidence", []))
        context_mode = build_context.get("mode", "unknown")
        critical_count = sum(
            1
            for field in (
                "requiredDeliverables",
                "allowedToolsAndAPIs",
                "requiredRepositoryFormat",
                "requiredDemoFormat",
                "requiredTechStackPieces",
            )
            for item in build_context.get(field, [])
            if item.get("priority") == "critical"
        )

        return {
            **append_step(
                state=state,
                node_name="retrieve_context",
                message="Retrieved structured RAG build context for the orchestrator.",
                decision_trace=[
                    f"Loaded build context via RAG adapter (mode={context_mode}).",
                    (
                        f"Indexed {index_summary.get('documentsLoaded', 0)} orchestrator URL document(s) "
                        f"({index_summary.get('chunksCreated', 0)} chunks) before retrieval."
                        if source_urls
                        else "No orchestrator source URLs to index (using ingested corpus and RAG_SCRAPE_URLS only)."
                    ),
                    f"Structured constraints: {len(build_context.get('requiredDeliverables', []))} deliverables, "
                    f"{len(build_context.get('requiredTechStackPieces', []))} stack items, "
                    f"{critical_count} critical priorities, {evidence_count} evidence chunks.",
                    f"Frontend intake title: {frontend_intake.title or 'not provided'}.",
                    f"Source context warnings: {source_context['sourceCounts']['warnings']}.",
                    f"Augmented with {len(docs)} retrieved doc matches and {len(memories)} memory matches.",
                ],
            ),
            "build_context": build_context,
            "retrieved_docs": docs,
            "memory_matches": memories,
        }

    async def scope_mvp(state: WorkflowState) -> dict[str, Any]:
        result = await active_model_client.complete_structured(
            purpose="scope_mvp",
            model=settings.nemotron_model,
            prompt=build_scope_mvp_prompt(
                idea=state["idea"],
                build_context=state.get("build_context", {}),
                memory_matches=state["memory_matches"],
            ),
            response_model=MvpScopeOutput,
            max_tokens=4000,
            reasoning_effort="medium",
        )
        scope = result.output.model_dump()
        return {
            **append_model_step(
                state=state,
                node_name="scope_mvp",
                message="Scoped the MVP to one judge-friendly workflow.",
                result=result,
            ),
            "mvp_scope": scope,
        }

    async def plan_repo(state: WorkflowState) -> dict[str, Any]:
        result = await active_model_client.complete_structured(
            purpose="plan_repo",
            model=settings.nemotron_model,
            prompt=build_plan_repo_prompt(
                idea=state["idea"],
                mvp_scope=state.get("mvp_scope", {}),
                build_context=state.get("build_context", {}),
            ),
            response_model=RepoPlanOutput,
            max_tokens=8000,
            reasoning_effort="medium",
        )
        plan = result.output.model_dump()
        return {
            **append_model_step(
                state=state,
                node_name="plan_repo",
                message="Planned the generated repository package.",
                result=result,
            ),
            "repo_plan": plan,
        }

    def create_repo(state: WorkflowState) -> dict[str, Any]:
        frontend_intake = FrontendIntake.model_validate(
            state.get("frontend_intake") or {"idea": state["idea"]}
        )
        repo_name = frontend_intake.repoName or _repo_name_from_url(frontend_intake.repoUrl)
        repo_description = (
            frontend_intake.repoDescription
            or frontend_intake.title
            or f"Generated MVPilot project for: {state['idea'][:120]}"
        )
        tool_call = active_tools.create_repo(
            task_id=state["task_id"],
            visibility=state["repo_visibility"],
            repo_preference=frontend_intake.repoPreference,
            repo_name=repo_name,
            repo_description=repo_description,
            repo_url=frontend_intake.repoUrl,
        )
        repo_step_status = "completed" if tool_call["status"] == "success" else "failed"
        update: dict[str, Any] = {
            **append_step(
                state=state,
                node_name="create_repo",
                status=repo_step_status,
                message=tool_call["summary"],
                decision_trace=[
                    (
                        "Used mock GitHub adapter instead of a live API call."
                        if state["mock_mode"]
                        else "Used the connected GitHub account for the requested repo action."
                    ),
                    f"Repository preference: {frontend_intake.repoPreference}.",
                    (
                        "Stored repo metadata for later commit steps."
                        if tool_call["status"] == "success"
                        else "Repository creation failed; workflow stopped before file generation."
                    ),
                ],
            ),
            "repo": tool_call["repo"],
            "tool_calls": [tool_call],
            "openclaw_trace": _openclaw_trace_from_tool_call(tool_call),
            "last_tool_result": tool_call,
        }
        if tool_call["status"] != "success":
            update["status"] = "failed"
            update["failure_reason"] = tool_call["summary"]
        return update

    async def generate_files(state: WorkflowState) -> dict[str, Any]:
        progress_steps: list[AgentStep] = []
        plan_result = await active_model_client.complete_structured(
            purpose="file_plan",
            model=settings.nemotron_model,
            prompt=build_file_plan_prompt(
                idea=state["idea"],
                repo_plan=state.get("repo_plan", {}),
                build_context=state.get("build_context", {}),
            ),
            response_model=FilePlanOutput,
            max_tokens=8000,
            reasoning_effort="medium",
        )
        plan_step = build_model_step(
            state=state,
            node_name="generate_files",
            message="Planned generated repo files.",
            result=plan_result,
            status="running",
            prompt_purpose="file_plan",
            extra_trace=[
                "Next step: generate each planned file as a separate model call.",
            ],
        )
        progress_steps.append(plan_step)
        await publish_progress(state, plan_step)
        plan = plan_result.output.model_dump()
        planned_artifacts = [
            {
                key: value
                for key, value in artifact.items()
                if key in {"name", "kind", "summary"}
            }
            for artifact in plan["artifacts"][:16]
        ]
        async def generate_one_file(artifact: dict[str, Any]) -> ModelCallResult:
            file_name = str(artifact.get("name") or "unknown file")
            start_step = AgentStep(
                project_id=state["task_id"],
                flight_stage=NODE_FLIGHT_STAGE.get("generate_files"),
                agent=NODE_AGENT.get("generate_files"),
                node_name="generate_files",
                status="running",
                message=f"Generating {file_name}.",
                model=settings.nemotron_model,
                prompt_purpose="file_content",
                model_mode=None,
                decision_trace=[
                    f"Started one-file generation for {file_name}.",
                    "This progress event is emitted before the model call returns.",
                ],
                timestamp=datetime.now(UTC),
            )
            progress_steps.append(start_step)
            await publish_progress(state, start_step)
            file_result = await active_model_client.complete_structured(
                purpose="file_content",
                model=settings.nemotron_model,
                prompt=build_file_content_prompt(
                    idea=state["idea"],
                    repo_plan=state.get("repo_plan", {}),
                    build_context=state.get("build_context", {}),
                    artifact=artifact,
                    file_plan=planned_artifacts,
                ),
                response_model=GeneratedFileOutput,
                max_tokens=10000,
                reasoning_effort="medium",
            )
            file_step = build_model_step(
                state=state,
                node_name="generate_files",
                message=f"Generated {file_result.output.name}.",
                result=file_result,
                status="running",
                prompt_purpose="file_content",
            )
            progress_steps.append(file_step)
            await publish_progress(state, file_step)
            return file_result

        semaphore = asyncio.Semaphore(3)

        async def generate_one_file_limited(artifact: dict[str, Any]) -> ModelCallResult:
            async with semaphore:
                return await generate_one_file(artifact)

        generated_file_results = list(
            await asyncio.gather(
                *(generate_one_file_limited(artifact) for artifact in planned_artifacts)
            )
        )
        generated_artifacts = [
            result.output.model_dump() for result in generated_file_results
        ]
        manifest = {
            "artifacts": generated_artifacts,
            "mode": _package_mode([plan_result, *generated_file_results]),
            "decision_trace": [
                *plan_result.output.decision_trace,
                *[
                    f"{result.output.name}: {result.mode}"
                    for result in generated_file_results
                ],
            ],
        }
        frontend_intake = FrontendIntake.model_validate(
            state.get("frontend_intake") or {"idea": state["idea"]}
        )
        manifest["artifacts"] = merge_with_project_artifacts(
            manifest["artifacts"],
            idea=state["idea"],
            title=frontend_intake.title or title_from_idea(state["idea"]),
            resolved_stack=_resolved_stack_summary(state.get("build_context", {})),
            repo_plan=state.get("repo_plan", {}),
            source_warnings=_source_warnings(state.get("build_context", {})),
        )
        artifacts = [
            {
                **artifact,
                "mock_mode": manifest["mode"] != "live",
                "summary": (
                    artifact["summary"]
                    if manifest["mode"] == "live"
                    else f"{manifest['mode'].title()} mode: {artifact['summary']}"
                ),
            }
            for artifact in manifest["artifacts"]
        ]
        combined_result = ModelCallResult(
            output=FileManifestOutput.model_validate(manifest),
            model=settings.nemotron_model,
            purpose="file_manifest",
            mode=manifest["mode"],
            latency_ms=sum(
                result.latency_ms for result in [plan_result, *generated_file_results]
            ),
            fallback_reason=next(
                (
                    result.fallback_reason
                    for result in [plan_result, *generated_file_results]
                    if result.fallback_reason
                ),
                None,
            ),
        )
        final_step = build_model_step(
            state=state,
            node_name="generate_files",
            message="Generated runnable frontend, backend, database, test, docs, and demo files.",
            result=combined_result,
            extra_trace=[
                f"Generated {len(generated_file_results)} file content payload(s) individually.",
            ],
        )
        return {
            "agent_steps": [*progress_steps, final_step],
            "graph_trace": [*progress_steps, final_step],
            "generated_artifacts": artifacts,
            "file_manifest": manifest,
        }

    def debug_generated_files(state: WorkflowState) -> dict[str, Any]:
        debug_report = _debug_generated_artifacts(state["generated_artifacts"])
        debug_artifact = {
            "name": "docs/DEBUG_REPORT.md",
            "kind": "markdown",
            "mock_mode": False,
            "summary": "Pre-commit debug report for generated files.",
            "content": debug_report["content"],
        }
        issue_count = len(debug_report["issues"])
        warning_count = len(debug_report["warnings"])
        return {
            **append_step(
                state=state,
                node_name="debug_generated_files",
                status="completed",
                message=(
                    "Ran pre-commit generated-file debug checks."
                    if issue_count == 0
                    else "Ran pre-commit generated-file debug checks with issues."
                ),
                decision_trace=[
                    f"Checked {len(state['generated_artifacts'])} generated artifact(s).",
                    f"Found {issue_count} issue(s) and {warning_count} warning(s).",
                    "Added docs/DEBUG_REPORT.md to make the debug pass visible in the repo.",
                ],
            ),
            "generated_artifacts": [debug_artifact],
        }

    def commit_progress(state: WorkflowState) -> dict[str, Any]:
        repo_name = state.get("repo", {}).get("name", "mvpilot-demo")
        files = merge_repo_health_scaffold(_files_from_generated_artifacts(state["generated_artifacts"]))
        tool_call = active_tools.commit_files(
            repo_name=repo_name,
            files=files,
            message="Add generated MVPilot project package",
        )
        update: dict[str, Any] = {
            **append_step(
                state=state,
                node_name="commit_progress",
                message=tool_call["summary"],
                decision_trace=[
                    f"Committed {len(files)} generated package file(s).",
                    (
                        "Recorded a deterministic commit SHA for dashboard traceability."
                        if state["mock_mode"]
                        else "Committed files using the connected GitHub account."
                    ),
                ],
            ),
            "tool_calls": [tool_call],
            "openclaw_trace": _openclaw_trace_from_tool_call(tool_call),
            "last_tool_result": tool_call,
        }
        if tool_call["status"] != "success":
            update["status"] = "failed"
            update["failure_reason"] = tool_call["summary"]
        return update

    def verify_build(state: WorkflowState) -> dict[str, Any]:
        repo_name = state.get("repo", {}).get("name")
        tool_call = active_tools.verify_build(
            recovered=state["blocker_recovered"],
            repo_name=repo_name,
        )
        status = "completed" if tool_call["status"] == "success" else "blocked"
        update: dict[str, Any] = {
            **append_step(
                state=state,
                node_name="verify_build",
                status=status,
                message=tool_call["summary"],
                decision_trace=[
                    (
                        "Ran deterministic mock build verification."
                        if state["mock_mode"]
                        else "Ran repository health verification against committed files."
                    ),
                    "Routed recoverable failures through the blocker handler.",
                ],
            ),
            "tool_calls": [tool_call],
            "openclaw_trace": _openclaw_trace_from_tool_call(tool_call),
            "last_tool_result": tool_call,
        }
        if tool_call["status"] != "success":
            update["failure_reason"] = (
                tool_call.get("error")
                or tool_call.get("summary")
                or "Generated repository health check failed."
            )
        return update

    async def handle_blocker(state: WorkflowState) -> dict[str, Any]:
        result = await active_model_client.complete_structured(
            purpose="blocker_analysis",
            model=settings.nemotron_model,
            prompt=build_blocker_analysis_prompt(
                idea=state["idea"],
                tool_result=state.get("last_tool_result", {}),
            ),
            response_model=BlockerAnalysisOutput,
            max_tokens=4000,
            reasoning_effort="medium",
        )
        blocker_analysis = result.output.model_dump()
        tool_call = active_tools.recover_build()
        return {
            **append_model_step(
                state=state,
                node_name="handle_blocker",
                message="Recovered from the mock build blocker.",
                result=result,
            ),
            "blocker_recovered": True,
            "blocker_analysis": blocker_analysis,
            "tool_calls": [tool_call],
            "openclaw_trace": _openclaw_trace_from_tool_call(tool_call),
            "last_tool_result": tool_call,
        }

    async def generate_final_package(state: WorkflowState) -> dict[str, Any]:
        readme_result = await active_model_client.complete_structured(
            purpose="final_readme",
            model=settings.nemotron_model,
            prompt=build_final_readme_prompt(
                idea=state["idea"],
                mvp_scope=state.get("mvp_scope", {}),
                repo_plan=state.get("repo_plan", {}),
                generated_artifacts=state["generated_artifacts"],
                build_context=state.get("build_context", {}),
            ),
            response_model=FinalReadmeOutput,
            max_tokens=4000,
            reasoning_effort="medium",
        )
        demo_result = await active_model_client.complete_structured(
            purpose="demo_script",
            model=settings.nemotron_model,
            prompt=build_demo_script_prompt(
                idea=state["idea"],
                blocker_analysis=state.get("blocker_analysis"),
                build_context=state.get("build_context", {}),
            ),
            response_model=DemoScriptOutput,
            max_tokens=3000,
            reasoning_effort="medium",
        )
        pitch_result = await active_model_client.complete_structured(
            purpose="pitch",
            model=settings.nemotron_model,
            prompt=build_pitch_prompt(
                idea=state["idea"],
                final_readme=readme_result.output.model_dump(),
                demo_script=demo_result.output.model_dump(),
                build_context=state.get("build_context", {}),
            ),
            response_model=PitchOutput,
            max_tokens=3000,
            reasoning_effort="medium",
        )
        package_mode = _package_mode([readme_result, demo_result, pitch_result])
        readme = readme_result.output.model_dump()
        demo_script = demo_result.output.model_dump()
        pitch = pitch_result.output.model_dump()
        source_warnings = _source_warnings(state.get("build_context", {}))
        last_commit = _last_tool_call(state, "github.commit_files")
        repo = state.get("repo") or {}
        commit_url = last_commit.get("commit_url")
        links = {
            "repoUrl": repo.get("url"),
            "commitUrl": commit_url,
            "branch": "main",
            "buildLogPath": "docs/BUILD_LOG.md",
            "architectureDocPath": "docs/ARCHITECTURE.md",
            "demoScriptPath": "demo/demo_script.md",
        }
        final_report = {
            "status": "completed",
            "mode": package_mode,
            "model": settings.nemotron_model,
            "repo": repo,
            "links": links,
            "github_result": last_commit or None,
            "summary": (
                f"{package_mode.title()} mode: Person 1 workflow produced a scoped MVP package with "
                "retrieval context, generated artifacts, and recovered build proof."
            ),
            "readme": readme,
            "demo_script": demo_script,
            "pitch": pitch,
            "blocker_analysis": state.get("blocker_analysis"),
            "source_warnings": source_warnings,
            "artifact_count": len(state["generated_artifacts"]) + 1,
        }
        final_artifact = {
            "name": "final_report.json",
            "kind": "json",
            "mock_mode": package_mode != "live",
            "summary": (
                f"{package_mode.title()} mode: generated final package report"
                f" with {len(source_warnings)} source warnings."
            ),
            "content": json_dumps_safe(final_report),
        }
        combined_result = ModelCallResult(
            output=pitch_result.output,
            model=settings.nemotron_model,
            purpose="final_package",
            mode=package_mode,
            latency_ms=(
                readme_result.latency_ms
                + demo_result.latency_ms
                + pitch_result.latency_ms
            ),
            fallback_reason=(
                readme_result.fallback_reason
                or demo_result.fallback_reason
                or pitch_result.fallback_reason
            ),
        )
        return {
            **append_model_step(
                state=state,
                node_name="generate_final_package",
                message="Generated the final package and report.",
                result=combined_result,
                prompt_purpose="final_package",
                extra_trace=[
                    "README synthesis completed.",
                    "Demo script synthesis completed.",
                    "Pitch synthesis completed.",
                ],
            ),
            "generated_artifacts": [final_artifact],
            "final_readme": readme,
            "demo_script": demo_script,
            "pitch": pitch,
            "final_report": final_report,
        }

    async def remember_outcome(state: WorkflowState) -> dict[str, Any]:
        final_report = state.get("final_report", {})
        summary = final_report.get("summary", "Workflow completed.")

        build_decisions = [
            {
                "node_name": step.node_name,
                "status": step.status,
                "message": step.message,
            }
            for step in state.get("graph_trace", [])
        ]
        payload = {
            "task_id": state["task_id"],
            "idea": state["idea"],
            "summary": summary,
            "outcome": {
                "mvp_scope": state.get("mvp_scope"),
                "repo_plan": state.get("repo_plan"),
                "blocker_analysis": state.get("blocker_analysis"),
                "file_tree": [artifact.get("name") for artifact in state.get("generated_artifacts", [])],
                "generated_artifacts": state.get("generated_artifacts"),
                "github_result": _last_tool_call(state, "github.commit_files") or _last_tool_call(state, "github.create_repo"),
                "build_decisions": build_decisions,
                "errors_and_fixes": state.get("blocker_analysis"),
                "final_report": final_report,
            },
            "tags": ["workflow_outcome"],
        }
        memory_trace = [
            "Captured plan, file tree, GitHub result summary, decisions, and final landing summary.",
        ]
        try:
            await active_retrieval.write_memory(payload)
            memory_trace.append("Wrote memory to storage.")
        except Exception as exc:
            memory_trace.append(f"Memory write skipped: {exc}")

        return append_step(
            state=state,
            node_name="remember_outcome",
            message="Stored the outcome for future retrieval.",
            decision_trace=memory_trace,
        )

    def report_result(state: WorkflowState) -> dict[str, Any]:
        return {
            **append_step(
                state=state,
                node_name="report_result",
                message="Reported the completed Person 1 workflow result.",
                decision_trace=[
                    "Marked the task completed after final package generation.",
                    "Exposed populated dashboard state through the existing API.",
                ],
            ),
            "status": "completed",
        }

    def failed(state: WorkflowState) -> dict[str, Any]:
        last_tool = state.get("last_tool_result") or {}
        reason = (
            state.get("failure_reason")
            or last_tool.get("error")
            or last_tool.get("summary")
            or (
                "Unrecoverable mock tool failure."
                if state["mock_mode"]
                else "Workflow stopped after an unrecoverable tool failure."
            )
        )
        final_report = {
            "status": "failed",
            "mode": "mock" if state["mock_mode"] else "live",
            "model": state["nemotron_model"],
            "summary": reason,
        }
        return {
            **append_step(
                state=state,
                node_name="failed",
                status="failed",
                message=reason,
                decision_trace=[
                    "Detected an unrecoverable tool result.",
                    "Stopped workflow execution and surfaced failure state.",
                ],
            ),
            "status": "failed",
            "final_report": final_report,
            "failure_reason": reason,
        }

    graph = StateGraph(WorkflowState)
    graph.add_node("receive_idea", receive_idea)
    graph.add_node("exchange_github_code", exchange_github_code)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("scope_mvp", scope_mvp)
    graph.add_node("plan_repo", plan_repo)
    graph.add_node("create_repo", create_repo)
    graph.add_node("generate_files", generate_files)
    graph.add_node("debug_generated_files", debug_generated_files)
    graph.add_node("commit_progress", commit_progress)
    graph.add_node("verify_build", verify_build)
    graph.add_node("handle_blocker", handle_blocker)
    graph.add_node("generate_final_package", generate_final_package)
    graph.add_node("remember_outcome", remember_outcome)
    graph.add_node("report_result", report_result)
    graph.add_node("failed", failed)
    graph.add_edge(START, "receive_idea")
    graph.add_edge("receive_idea", "exchange_github_code")
    graph.add_conditional_edges(
        "exchange_github_code",
        route_after_github_exchange,
        {
            "retrieve_context": "retrieve_context",
            "failed": "failed",
        },
    )
    graph.add_edge("retrieve_context", "scope_mvp")
    graph.add_edge("scope_mvp", "plan_repo")
    graph.add_edge("plan_repo", "create_repo")
    graph.add_conditional_edges(
        "create_repo",
        route_after_create_repo,
        {
            "generate_files": "generate_files",
            "failed": "failed",
        },
    )
    graph.add_edge("generate_files", "debug_generated_files")
    graph.add_edge("debug_generated_files", "commit_progress")
    graph.add_conditional_edges(
        "commit_progress",
        route_after_commit_progress,
        {
            "verify_build": "verify_build",
            "failed": "failed",
        },
    )
    graph.add_conditional_edges(
        "verify_build",
        route_after_tool_result,
        {
            "generate_final_package": "generate_final_package",
            "handle_blocker": "handle_blocker",
            "failed": "failed",
        },
    )
    graph.add_edge("handle_blocker", "verify_build")
    graph.add_edge("generate_final_package", "remember_outcome")
    graph.add_edge("remember_outcome", "report_result")
    graph.add_edge("report_result", END)
    graph.add_edge("failed", END)
    return graph.compile()


def _build_default_model_client(settings: Settings) -> ModelClient:
    if settings.mock_mode:
        return DeterministicModelClient(mode="mock")
    return NemotronModelClient(settings)


def _package_mode(results: list[ModelCallResult]) -> Literal["mock", "live", "fallback"]:
    modes = {result.mode for result in results}
    if "fallback" in modes:
        return "fallback"
    if modes == {"live"}:
        return "live"
    return "mock"


def _source_warnings(build_context: dict[str, Any]) -> list[dict[str, str]]:
    source_context = build_context.get("sourceContext", {})
    warnings = source_context.get("warnings") if isinstance(source_context, dict) else []
    return [warning for warning in warnings if isinstance(warning, dict)]


def _resolved_stack_summary(build_context: dict[str, Any]) -> str:
    resolved_stack = build_context.get("resolvedTechStack", {})
    items = resolved_stack.get("items") if isinstance(resolved_stack, dict) else None
    if isinstance(items, list):
        stack_items = [str(item).strip() for item in items if str(item).strip()]
        if stack_items:
            return ", ".join(stack_items)
    return "React, FastAPI, Supabase Postgres, Pytest"


def _openclaw_trace_from_tool_call(tool_call: dict[str, Any]) -> list[dict[str, Any]]:
    trace = tool_call.get("openclaw_trace", [])
    return [entry for entry in trace if isinstance(entry, dict)]


def _files_from_generated_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for artifact in artifacts:
        path = str(artifact.get("name") or "").strip()
        if not path or path.endswith("/"):
            continue
        if path.split("/")[-1] == ".env":
            continue

        content = artifact.get("content")
        if content is None:
            content = artifact.get("summary", "")
        if not isinstance(content, str):
            content = json.dumps(content, indent=2, sort_keys=True)
        files.append({"path": path, "content": content})

    return files


def _debug_generated_artifacts(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    files = _files_from_generated_artifacts(artifacts)
    paths = {file["path"] for file in files}
    content_by_path = {file["path"]: file["content"] for file in files}
    issues: list[str] = []
    warnings: list[str] = []

    required_paths = ["README.md", "docs/ARCHITECTURE.md", "demo/demo_script.md"]
    for path in required_paths:
        if path not in paths:
            issues.append(f"Missing required file: `{path}`.")

    if not any(path in paths for path in ("package.json", "requirements.txt")):
        issues.append("Missing a runnable dependency manifest: `package.json` or `requirements.txt`.")
    if not any(path.startswith(("src/", "backend/")) for path in paths):
        issues.append("Missing application source under `src/` or `backend/`.")
    if "package.json" in paths and not any(path.startswith("src/") for path in paths):
        warnings.append("`package.json` exists, but no frontend `src/` files were generated.")
    if "requirements.txt" in paths and not any(path.startswith("backend/") for path in paths):
        warnings.append("`requirements.txt` exists, but no `backend/` files were generated.")

    for path, content in content_by_path.items():
        if not content.strip():
            issues.append(f"Empty generated file: `{path}`.")
        if path.split("/")[-1] == ".env":
            issues.append(f"Unsafe real env file was generated: `{path}`.")
        if "TODO: implement" in content or "placeholder" in content.lower():
            warnings.append(f"Possible placeholder content in `{path}`.")
        if path == "package.json":
            try:
                package_json = json.loads(content)
            except json.JSONDecodeError:
                issues.append("`package.json` is not valid JSON.")
            else:
                package_issues, package_warnings = _debug_frontend_dependencies(
                    package_json
                )
                issues.extend(package_issues)
                warnings.extend(package_warnings)

    status = "passed" if not issues else "needs attention"
    lines = [
        "# Debug Report",
        "",
        f"Status: {status}",
        f"Files checked: {len(files)}",
        f"Issues: {len(issues)}",
        f"Warnings: {len(warnings)}",
        "",
        "## Issues",
        "",
        *(f"- {issue}" for issue in issues),
        *(["- None"] if not issues else []),
        "",
        "## Warnings",
        "",
        *(f"- {warning}" for warning in warnings),
        *(["- None"] if not warnings else []),
        "",
        "## Checked Files",
        "",
        *(f"- `{path}`" for path in sorted(paths)),
        "",
    ]
    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "content": "\n".join(lines),
    }


def _debug_frontend_dependencies(package_json: Any) -> tuple[list[str], list[str]]:
    if not isinstance(package_json, dict):
        return ["`package.json` must be a JSON object."], []

    deps = package_json.get("dependencies")
    dev_deps = package_json.get("devDependencies")
    all_deps: dict[str, str] = {}
    for section in (deps, dev_deps):
        if isinstance(section, dict):
            all_deps.update(
                {
                    str(name): str(version)
                    for name, version in section.items()
                    if isinstance(name, str)
                }
            )

    issues: list[str] = []
    warnings: list[str] = []
    minimum_majors = {
        "vite": 8,
        "@vitejs/plugin-react": 6,
        "react": 19,
        "react-dom": 19,
    }
    for package_name, minimum_major in minimum_majors.items():
        version = all_deps.get(package_name)
        if version is None:
            if package_name in {"vite", "react", "react-dom"}:
                issues.append(f"Missing frontend dependency `{package_name}`.")
            else:
                warnings.append(f"Missing frontend helper dependency `{package_name}`.")
            continue
        major = _major_version(version)
        if major is None:
            warnings.append(
                f"Could not verify `{package_name}` version `{version}`."
            )
            continue
        if major < minimum_major:
            issues.append(
                f"`{package_name}` is pinned to `{version}`; expected major {minimum_major} or newer."
            )

    react_version = all_deps.get("react")
    react_dom_version = all_deps.get("react-dom")
    if react_version and react_dom_version and react_version != react_dom_version:
        warnings.append(
            f"`react` ({react_version}) and `react-dom` ({react_dom_version}) should match."
        )

    if "vite" in all_deps and "@vitejs/plugin-react" in all_deps:
        vite_major = _major_version(all_deps["vite"])
        plugin_major = _major_version(all_deps["@vitejs/plugin-react"])
        if vite_major is not None and plugin_major is not None:
            if vite_major >= 8 and plugin_major < 6:
                issues.append(
                    "Vite 8 generated apps should use `@vitejs/plugin-react` major 6 or newer."
                )

    return issues, warnings


def _major_version(version: str) -> int | None:
    cleaned = version.strip()
    for prefix in ("^", "~", ">=", "<=", ">", "<", "="):
        cleaned = cleaned.removeprefix(prefix).strip()
    first = cleaned.split(".", 1)[0]
    return int(first) if first.isdigit() else None


def _last_tool_call(state: WorkflowState, tool_name: str) -> dict[str, Any]:
    for call in reversed(state.get("tool_calls", [])):
        raw_result = call.get("raw_result") if isinstance(call, dict) else None
        raw_tool_name = raw_result.get("tool_name") if isinstance(raw_result, dict) else None
        if call.get("tool") == tool_name or raw_tool_name == tool_name:
            return call
    return {}


def _repo_name_from_url(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    name = repo_url.rstrip("/").split("/")[-1].strip()
    return name or None


def json_dumps_safe(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def route_after_tool_result(state: dict[str, Any]) -> str:
    result = state.get("last_tool_result") or {}
    if result.get("status") == "success":
        return "generate_final_package"
    if result.get("recoverable") is True:
        return "handle_blocker"
    return "failed"


def route_after_github_exchange(state: dict[str, Any]) -> str:
    if state.get("status") == "failed":
        return "failed"
    return "retrieve_context"


def route_after_create_repo(state: dict[str, Any]) -> str:
    if state.get("status") == "failed":
        return "failed"
    return "generate_files"


def route_after_commit_progress(state: dict[str, Any]) -> str:
    if state.get("status") == "failed":
        return "failed"
    return "verify_build"
