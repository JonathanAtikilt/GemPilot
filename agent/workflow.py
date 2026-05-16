from __future__ import annotations

import operator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.config import Settings
from agent.schemas import AgentStep

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
    memory_matches: ListReducer
    tool_calls: ListReducer
    generated_artifacts: ListReducer
    last_tool_result: NotRequired[dict[str, Any]]
    repo: NotRequired[dict[str, Any]]
    mvp_scope: NotRequired[dict[str, Any]]
    repo_plan: NotRequired[dict[str, Any]]
    final_report: NotRequired[dict[str, Any] | None]
    failure_reason: NotRequired[str | None]


class MockAuditAdapter:
    def __init__(self, *, model_name: str) -> None:
        self._model_name = model_name

    def step(
        self,
        *,
        node_name: str,
        message: str,
        decision_trace: list[str],
        status: str = "completed",
    ) -> AgentStep:
        return AgentStep(
            node_name=node_name,
            status=status,
            message=message,
            model=self._model_name,
            decision_trace=[
                "Mock mode: deterministic Nemotron-style reasoning.",
                *decision_trace,
            ],
            timestamp=datetime.now(UTC),
        )


class MockRetrievalAdapter:
    def retrieve(self, idea: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        docs = [
            {
                "source": "hackathon_brief",
                "title": "MVPilot healthcare demo lane",
                "snippet": (
                    "Mock mode: prioritize a visible referral workflow, judge-ready "
                    "README, and short pitch package."
                ),
                "query": idea,
                "score": 0.94,
            },
            {
                "source": "nvidia_reference",
                "title": "Nemotron reasoning pattern",
                "snippet": (
                    "Mock mode: every agent step should expose model name and a "
                    "compact decision trace."
                ),
                "score": 0.91,
            },
        ]
        memories = [
            {
                "source": "previous_demo",
                "summary": (
                    "Mock mode: healthcare referral demos land better when blockers "
                    "show recovery instead of a perfect run."
                ),
                "score": 0.88,
            },
            {
                "source": "team_split",
                "summary": (
                    "Mock mode: Person 1 owns orchestration and produces artifacts "
                    "for downstream UI/demo surfaces."
                ),
                "score": 0.84,
            },
        ]
        return docs, memories


class MockToolAdapter:
    def create_repo(
        self,
        *,
        task_id: str,
        visibility: str,
    ) -> dict[str, Any]:
        repo_name = f"mvpilot-demo-{task_id[:8]}"
        return {
            "tool": "github.create_repo",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "repo": {
                "name": repo_name,
                "visibility": visibility,
                "url": f"https://github.com/mock-org/{repo_name}",
            },
            "summary": "Mock mode: created deterministic GitHub repository record.",
        }

    def commit_files(
        self,
        *,
        repo_name: str,
        files: list[str],
    ) -> dict[str, Any]:
        return {
            "tool": "github.commit_files",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "repo": repo_name,
            "files": files,
            "commit_sha": "mock-commit-0001",
            "summary": "Mock mode: committed generated MVP package files.",
        }

    def verify_build(self, *, recovered: bool) -> dict[str, Any]:
        if not recovered:
            return {
                "tool": "build.verify",
                "status": "failed",
                "mock_mode": True,
                "recoverable": True,
                "error": "Mock mode: missing demo dependency in generated package.",
                "summary": "Mock mode: build failed with a recoverable dependency gap.",
            }
        return {
            "tool": "build.verify",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "checks": ["unit", "lint", "package"],
            "summary": "Mock mode: build verification passed after recovery.",
        }

    def recover_build(self) -> dict[str, Any]:
        return {
            "tool": "build.apply_recovery_patch",
            "status": "success",
            "mock_mode": True,
            "recoverable": False,
            "patch": "Add deterministic demo dependency stub.",
            "summary": "Mock mode: applied recovery patch for the blocked build.",
        }


def build_initial_state(
    *,
    task_id: str,
    idea: str,
    repo_visibility: Literal["public", "private"],
    demo_mode: bool,
    settings: Settings,
) -> WorkflowState:
    return {
        "task_id": task_id,
        "idea": idea,
        "repo_visibility": repo_visibility,
        "demo_mode": demo_mode,
        "status": "started",
        "nemotron_model": settings.nemotron_fast_model,
        "mock_mode": True,
        "blocker_recovered": False,
        "agent_steps": [],
        "graph_trace": [],
        "retrieved_docs": [],
        "memory_matches": [],
        "tool_calls": [],
        "generated_artifacts": [],
        "final_report": None,
        "failure_reason": None,
    }


def build_workflow(
    settings: Settings,
    *,
    audit: MockAuditAdapter | None = None,
    retrieval: MockRetrievalAdapter | None = None,
    tools: MockToolAdapter | None = None,
):
    active_audit = audit or MockAuditAdapter(model_name=settings.nemotron_fast_model)
    active_retrieval = retrieval or MockRetrievalAdapter()
    active_tools = tools or MockToolAdapter()

    def append_step(
        *,
        node_name: str,
        message: str,
        decision_trace: list[str],
        status: str = "completed",
    ) -> dict[str, list[AgentStep]]:
        step = active_audit.step(
            node_name=node_name,
            message=message,
            decision_trace=decision_trace,
            status=status,
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

    def retrieve_context(state: WorkflowState) -> dict[str, Any]:
        docs, memories = active_retrieval.retrieve(state["idea"])
        return {
            **append_step(
                node_name="retrieve_context",
                message="Retrieved hackathon guidance and prior memory matches.",
                decision_trace=[
                    "Seeded context from deterministic RAG snippets.",
                    "Selected healthcare demo memories tied to blocker recovery.",
                ],
            ),
            "retrieved_docs": docs,
            "memory_matches": memories,
        }

    def scope_mvp(state: WorkflowState) -> dict[str, Any]:
        scope = {
            "target_user": "clinic referral coordinator",
            "must_have": [
                "intake summary",
                "blocked referral detection",
                "next-best follow-up plan",
            ],
            "demo_boundary": "single mocked clinic workflow",
            "mode": "mock",
        }
        return {
            **append_step(
                node_name="scope_mvp",
                message="Scoped the MVP to a judge-friendly referral workflow.",
                decision_trace=[
                    "Focused on one healthcare referral pain point.",
                    "Limited external integrations to mock adapters for Feature 2.",
                ],
            ),
            "mvp_scope": scope,
        }

    def plan_repo(state: WorkflowState) -> dict[str, Any]:
        plan = {
            "files": ["README.md", "demo_script.md", "pitch.md"],
            "test_plan": ["unit workflow", "API integration", "mock build verify"],
            "mode": "mock",
        }
        return {
            **append_step(
                node_name="plan_repo",
                message="Planned the generated repository package.",
                decision_trace=[
                    "Chose a small artifact set that proves the workflow.",
                    "Kept generated files deterministic for stable tests.",
                ],
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

    def generate_files(state: WorkflowState) -> dict[str, Any]:
        artifacts = [
            {
                "name": "README.md",
                "kind": "markdown",
                "mock_mode": True,
                "summary": "Mock mode: generated setup and referral agent overview.",
            },
            {
                "name": "demo_script.md",
                "kind": "markdown",
                "mock_mode": True,
                "summary": "Mock mode: generated a three-minute demo script.",
            },
            {
                "name": "pitch.md",
                "kind": "markdown",
                "mock_mode": True,
                "summary": "Mock mode: generated a concise hackathon pitch.",
            },
        ]
        return {
            **append_step(
                node_name="generate_files",
                message="Generated README, demo script, and pitch artifacts.",
                decision_trace=[
                    "Mapped retrieved context into repo artifacts.",
                    "Kept content summaries visible instead of writing a real repo.",
                ],
            ),
            "generated_artifacts": artifacts,
        }

    def commit_progress(state: WorkflowState) -> dict[str, Any]:
        repo_name = state.get("repo", {}).get("name", "mvpilot-demo")
        files = [artifact["name"] for artifact in state["generated_artifacts"]]
        tool_call = active_tools.commit_files(repo_name=repo_name, files=files)
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

    def handle_blocker(state: WorkflowState) -> dict[str, Any]:
        tool_call = active_tools.recover_build()
        return {
            **append_step(
                node_name="handle_blocker",
                message="Recovered from the mock build blocker.",
                decision_trace=[
                    "Classified the tool failure as recoverable.",
                    "Applied the smallest deterministic recovery patch.",
                ],
            ),
            "blocker_recovered": True,
            "tool_calls": [tool_call],
            "last_tool_result": tool_call,
        }

    def generate_final_package(state: WorkflowState) -> dict[str, Any]:
        final_report = {
            "status": "completed",
            "mode": "mock",
            "model": state["nemotron_model"],
            "repo": state.get("repo"),
            "summary": (
                "Mock mode: Person 1 workflow produced a scoped MVP package with "
                "retrieval context, generated artifacts, and recovered build proof."
            ),
            "artifact_count": len(state["generated_artifacts"]) + 1,
        }
        final_artifact = {
            "name": "final_report.json",
            "kind": "json",
            "mock_mode": True,
            "summary": "Mock mode: generated final package report.",
        }
        return {
            **append_step(
                node_name="generate_final_package",
                message="Generated the final package and report.",
                decision_trace=[
                    "Collected repo, retrieval, build, and artifact evidence.",
                    "Labeled the result as mock mode for Feature 2.",
                ],
            ),
            "generated_artifacts": [final_artifact],
            "final_report": final_report,
        }

    def remember_outcome(state: WorkflowState) -> dict[str, Any]:
        return append_step(
            node_name="remember_outcome",
            message="Stored the mock outcome for future retrieval.",
            decision_trace=[
                "Captured recovery pattern as a reusable memory note.",
                "Kept persistence mocked until the live adapter feature.",
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


def route_after_tool_result(state: dict[str, Any]) -> str:
    result = state.get("last_tool_result") or {}
    if result.get("status") == "success":
        return "generate_final_package"
    if result.get("recoverable") is True:
        return "handle_blocker"
    return "failed"
