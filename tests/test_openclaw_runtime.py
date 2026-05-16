from agent.config import Settings
from agent.adapters import InMemoryToolAdapter
from agent.openclaw_runtime import (
    OpenClawToolAdapter,
    openclaw_runtime_status,
    registered_openclaw_tools,
)


def test_openclaw_status_requires_api_key() -> None:
    missing = openclaw_runtime_status(Settings(_env_file=None))
    configured = openclaw_runtime_status(
        Settings(_env_file=None, openclaw_api_key="fake-openclaw-key")
    )

    assert missing["openclaw_runtime_ready"] is False
    assert missing["openclaw_registered_tools"] == []
    assert configured["openclaw_runtime_ready"] is True
    assert "github.create_repo" in configured["openclaw_registered_tools"]


def test_registered_openclaw_tools_include_person3_tools() -> None:
    tools = registered_openclaw_tools()

    assert "github.create_repo" in tools
    assert "github.commit_files" in tools
    assert "github.append_build_log" in tools
    assert "github.verify_commit" in tools
    assert "build.detect_blocker" in tools


def test_openclaw_tool_adapter_marks_tool_results() -> None:
    adapter = OpenClawToolAdapter(InMemoryToolAdapter(), environment="development")

    result = adapter.create_repo("task-12345678", "private")

    assert result["runtime"] == "openclaw"
    assert result["openclaw_tool"] == "github.create_repo"
    assert result["openclaw_trace"][0]["environment"] == "development"
    assert result["openclaw_trace"][0]["tool"] == "github.create_repo"
    assert result["repo"]["visibility"] == "private"


def test_openclaw_tool_adapter_exposes_build_log_tool(monkeypatch) -> None:
    monkeypatch.setenv("MVPILOT_MOCK_TOOLS", "true")
    adapter = OpenClawToolAdapter(InMemoryToolAdapter(), environment="development")

    result = adapter.append_build_log(
        task_id="task-1",
        repo_name="mvpilot-generated-demo",
        message="Created repo",
        data={"step": 1},
    )

    assert result["runtime"] == "openclaw"
    assert result["openclaw_tool"] == "github.append_build_log"
    assert result["status"] == "mock"
