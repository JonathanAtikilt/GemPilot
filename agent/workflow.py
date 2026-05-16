from __future__ import annotations

import operator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, NotRequired, TypedDict

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
    FileManifestOutput,
    FinalReadmeOutput,
    MvpScopeOutput,
    PitchOutput,
    RepoPlanOutput,
)
from agent.prompts import (
    build_blocker_analysis_prompt,
    build_demo_script_prompt,
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
from agent.live_adapters import LiveRagMemoryAdapter
from agent.schemas import UploadedSourceFileContent

ListReducer = Annotated[list[dict[str, Any]], operator.add]
StepReducer = Annotated[list[AgentStep], operator.add]


class WorkflowState(TypedDict):
    task_id: str
    idea: str
    repo_visibility: Literal["public", "private"]
    demo_mode: bool
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
    frontend_intake: dict[str, Any] | None = None,
    uploaded_file_contents: list[dict[str, Any]] | None = None,
) -> WorkflowState:
    normalized_intake = frontend_intake or FrontendIntake(idea=idea).model_dump()
    return {
        "task_id": task_id,
        "idea": idea,
        "repo_visibility": repo_visibility,
        "demo_mode": demo_mode,
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
):
    active_audit = audit or InMemoryAuditAdapter(model_name=settings.nemotron_fast_model)
    active_model_client = model_client or _build_default_model_client(settings)
    active_retrieval = retrieval or LiveRagMemoryAdapter()
    active_tools = tools or InMemoryToolAdapter()

    def append_step(
        *,
        node_name: str,
        message: str,
        decision_trace: list[str],
        status: str = "completed",
    ) -> dict[str, list[AgentStep]]:
        step = active_audit.write_audit_log(
            node_name=node_name,
            message=message,
            decision_trace=decision_trace,
            status=status,
        )
        return {"agent_steps": [step], "graph_trace": [step]}

    def append_model_step(
        *,
        node_name: str,
        message: str,
        result: ModelCallResult,
        status: str = "completed",
        prompt_purpose: str | None = None,
        extra_trace: list[str] | None = None,
    ) -> dict[str, list[AgentStep]]:
        step = AgentStep(
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
        return {"agent_steps": [step], "graph_trace": [step]}

    def receive_idea(state: WorkflowState) -> dict[str, Any]:
        return append_step(
            node_name="receive_idea",
            message="Received the idea and initialized the Person 1 workflow.",
            decision_trace=[
                "Accepted the trimmed idea payload.",
                "Kept endpoint response shape unchanged.",
                f"Demo mode is {state['demo_mode']}.",
            ],
        )

    async def retrieve_context(state: WorkflowState) -> dict[str, Any]:
        frontend_intake = FrontendIntake.model_validate(
            state.get("frontend_intake") or {"idea": state["idea"]}
        )
        build_context = await active_retrieval.retrieve_build_context(
            state["task_id"],
            state["idea"],
            optional_params=build_optional_params_from_frontend_intake(frontend_intake),
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
                node_name="retrieve_context",
                message="Retrieved structured RAG build context for the orchestrator.",
                decision_trace=[
                    f"Loaded build context via RAG adapter (mode={context_mode}).",
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
            max_tokens=900,
            reasoning_effort="medium",
        )
        scope = result.output.model_dump()
        return {
            **append_model_step(
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
            max_tokens=900,
            reasoning_effort="medium",
        )
        plan = result.output.model_dump()
        return {
            **append_model_step(
                node_name="plan_repo",
                message="Planned the generated repository package.",
                result=result,
            ),
            "repo_plan": plan,
        }

    def create_repo(state: WorkflowState) -> dict[str, Any]:
        tool_call = active_tools.create_repo(
            task_id=state["task_id"],
            visibility=state["repo_visibility"],
        )
        return {
            **append_step(
                node_name="create_repo",
                message="Created the mock GitHub repository record.",
                decision_trace=[
                    "Used mock GitHub adapter instead of a live API call.",
                    "Stored repo metadata for later commit steps.",
                ],
            ),
            "repo": tool_call["repo"],
            "tool_calls": [tool_call],
            "last_tool_result": tool_call,
        }

    async def generate_files(state: WorkflowState) -> dict[str, Any]:
        result = await active_model_client.complete_structured(
            purpose="file_manifest",
            model=settings.nemotron_fast_model,
            prompt=build_file_manifest_prompt(
                idea=state["idea"],
                repo_plan=state.get("repo_plan", {}),
                build_context=state.get("build_context", {}),
            ),
            response_model=FileManifestOutput,
            max_tokens=1200,
            reasoning_effort="low",
        )
        manifest = result.output.model_dump()
        artifacts = [
            {
                **artifact,
                "mock_mode": result.mode != "live",
                "summary": (
                    artifact["summary"]
                    if result.mode == "live"
                    else f"{result.mode.title()} mode: {artifact['summary']}"
                ),
            }
            for artifact in manifest["artifacts"]
        ]
        return {
            **append_model_step(
                node_name="generate_files",
                message="Generated README, demo script, and pitch artifacts.",
                result=result,
            ),
            "generated_artifacts": artifacts,
            "file_manifest": manifest,
        }

    def commit_progress(state: WorkflowState) -> dict[str, Any]:
        repo_name = state.get("repo", {}).get("name", "mvpilot-demo")
        files = [
            {"path": artifact["name"], "content": f"Mock content for {artifact['name']}"}
            for artifact in state["generated_artifacts"]
        ]
        tool_call = active_tools.commit_files(repo_name=repo_name, files=files, message="Add generated artifacts")
        return {
            **append_step(
                node_name="commit_progress",
                message="Committed generated artifacts through the mock tool adapter.",
                decision_trace=[
                    "Committed only generated package files.",
                    "Recorded a deterministic commit SHA for dashboard traceability.",
                ],
            ),
            "tool_calls": [tool_call],
            "last_tool_result": tool_call,
        }

    def verify_build(state: WorkflowState) -> dict[str, Any]:
        tool_call = active_tools.verify_build(recovered=state["blocker_recovered"])
        status = "completed" if tool_call["status"] == "success" else "blocked"
        return {
            **append_step(
                node_name="verify_build",
                status=status,
                message=tool_call["summary"],
                decision_trace=[
                    "Ran deterministic mock build verification.",
                    "Routed recoverable failures through the blocker handler.",
                ],
            ),
            "tool_calls": [tool_call],
            "last_tool_result": tool_call,
        }

    async def handle_blocker(state: WorkflowState) -> dict[str, Any]:
        result = await active_model_client.complete_structured(
            purpose="blocker_analysis",
            model=settings.nemotron_model,
            prompt=build_blocker_analysis_prompt(
                idea=state["idea"],
                tool_result=state.get("last_tool_result", {}),
            ),
            response_model=BlockerAnalysisOutput,
            max_tokens=900,
            reasoning_effort="medium",
        )
        blocker_analysis = result.output.model_dump()
        tool_call = active_tools.recover_build()
        return {
            **append_model_step(
                node_name="handle_blocker",
                message="Recovered from the mock build blocker.",
                result=result,
            ),
            "blocker_recovered": True,
            "blocker_analysis": blocker_analysis,
            "tool_calls": [tool_call],
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
            max_tokens=1400,
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
            max_tokens=1100,
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
            max_tokens=1100,
            reasoning_effort="medium",
        )
        package_mode = _package_mode([readme_result, demo_result, pitch_result])
        readme = readme_result.output.model_dump()
        demo_script = demo_result.output.model_dump()
        pitch = pitch_result.output.model_dump()
        source_warnings = _source_warnings(state.get("build_context", {}))
        final_report = {
            "status": "completed",
            "mode": package_mode,
            "model": settings.nemotron_model,
            "repo": state.get("repo"),
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
        
        payload = {
            "task_id": state["task_id"],
            "idea": state["idea"],
            "summary": summary,
            "outcome": {
                "mvp_scope": state.get("mvp_scope"),
                "repo_plan": state.get("repo_plan"),
                "blocker_analysis": state.get("blocker_analysis"),
                "generated_artifacts": state.get("generated_artifacts"),
                "final_report": final_report,
            },
            "tags": ["workflow_outcome"],
        }
        await active_retrieval.write_memory(payload)
        
        return append_step(
            node_name="remember_outcome",
            message="Stored the outcome for future retrieval.",
            decision_trace=[
                "Captured recovery pattern as a reusable memory note.",
                "Wrote memory to storage.",
            ],
        )

    def report_result(state: WorkflowState) -> dict[str, Any]:
        return {
            **append_step(
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
        reason = state.get("failure_reason") or "Unrecoverable mock tool failure."
        final_report = {
            "status": "failed",
            "mode": "mock",
            "model": state["nemotron_model"],
            "summary": reason,
        }
        return {
            **append_step(
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
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("scope_mvp", scope_mvp)
    graph.add_node("plan_repo", plan_repo)
    graph.add_node("create_repo", create_repo)
    graph.add_node("generate_files", generate_files)
    graph.add_node("commit_progress", commit_progress)
    graph.add_node("verify_build", verify_build)
    graph.add_node("handle_blocker", handle_blocker)
    graph.add_node("generate_final_package", generate_final_package)
    graph.add_node("remember_outcome", remember_outcome)
    graph.add_node("report_result", report_result)
    graph.add_node("failed", failed)
    graph.add_edge(START, "receive_idea")
    graph.add_edge("receive_idea", "retrieve_context")
    graph.add_edge("retrieve_context", "scope_mvp")
    graph.add_edge("scope_mvp", "plan_repo")
    graph.add_edge("plan_repo", "create_repo")
    graph.add_edge("create_repo", "generate_files")
    graph.add_edge("generate_files", "commit_progress")
    graph.add_edge("commit_progress", "verify_build")
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


def route_after_tool_result(state: dict[str, Any]) -> str:
    result = state.get("last_tool_result") or {}
    if result.get("status") == "success":
        return "generate_final_package"
    if result.get("recoverable") is True:
        return "handle_blocker"
    return "failed"
