import asyncio
from uuid import UUID, uuid4


VALID_IDEA = (
    "Build a healthcare referral coordination agent that helps clinics "
    "prevent failed referrals."
)
FRONTEND_IDEA = "Build a study planner that turns messy class notes into a weekly review plan."


def start_task(client) -> str:
    response = client.post(
        "/agent/run",
        json={
            "idea": VALID_IDEA,
            "repo_visibility": "public",
            "demo_mode": True,
        },
    )
    assert response.status_code == 202
    return response.json()["task_id"]


def test_run_agent_accepts_valid_healthcare_referral_idea(client):
    response = client.post(
        "/agent/run",
        json={
            "idea": f"  {VALID_IDEA}  ",
            "repo_visibility": "public",
            "demo_mode": True,
        },
    )

    assert response.status_code == 202
    data = response.json()
    UUID(data["task_id"])
    assert data["status"] == "started"


def test_run_agent_accepts_frontend_form_payload_without_healthcare_mock(client):
    response = client.post(
        "/agent/run",
        data={
            "title": "Study planner",
            "idea": f"  {FRONTEND_IDEA}  ",
            "rule_source_type": "url",
            "rules_url": "https://example.com/hackathon-rules",
            "source": "mvpilot_frontend",
        },
    )

    assert response.status_code == 202
    task_id = response.json()["task_id"]

    detail_response = client.get(f"/agent/tasks/{task_id}")
    assert detail_response.status_code == 200
    data = detail_response.json()
    assert data["task"]["idea"] == FRONTEND_IDEA
    assert data["task"]["repo_visibility"] == "public"
    assert data["final_report"]["readme"]["content"].count(FRONTEND_IDEA) >= 1
    assert "healthcare" not in data["final_report"]["readme"]["content"].lower()


def test_run_agent_defaults_demo_mode_to_false(client):
    response = client.post(
        "/agent/run",
        json={"idea": VALID_IDEA, "repo_visibility": "private"},
    )

    assert response.status_code == 202
    task_id = response.json()["task_id"]

    detail_response = client.get(f"/agent/tasks/{task_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["task"]["demo_mode"] is False


def test_run_agent_rejects_blank_ideas(client):
    response = client.post(
        "/agent/run",
        json={"idea": "   ", "repo_visibility": "public"},
    )

    assert response.status_code == 422


def test_run_agent_rejects_invalid_repo_visibility(client):
    response = client.post(
        "/agent/run",
        json={"idea": VALID_IDEA, "repo_visibility": "internal"},
    )

    assert response.status_code == 422


def test_task_detail_returns_populated_workflow_dashboard(client):
    task_id = start_task(client)

    response = client.get(f"/agent/tasks/{task_id}")

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "task",
        "agent_steps",
        "retrieved_docs",
        "memory_matches",
        "tool_calls",
        "approvals",
        "generated_artifacts",
        "graph_trace",
        "final_report",
    }
    assert data["task"]["id"] == task_id
    assert data["task"]["idea"] == VALID_IDEA
    assert data["task"]["repo_visibility"] == "public"
    assert data["task"]["demo_mode"] is True
    assert data["task"]["status"] == "completed"
    assert data["retrieved_docs"]
    assert data["memory_matches"]
    assert [tool_call["tool"] for tool_call in data["tool_calls"]] == [
        "github.create_repo",
        "github.commit_files",
        "build.verify",
        "build.apply_recovery_patch",
        "build.verify",
    ]
    assert data["approvals"] == []
    assert {artifact["name"] for artifact in data["generated_artifacts"]} >= {
        "README.md",
        "demo_script.md",
        "pitch.md",
        "final_report.json",
    }
    assert data["final_report"]["status"] == "completed"
    assert data["final_report"]["readme"]["content"]
    assert data["final_report"]["demo_script"]["content"]
    assert data["final_report"]["pitch"]["content"]
    assert data["final_report"]["blocker_analysis"]["blocker_type"]
    assert [step["node_name"] for step in data["graph_trace"]] == [
        "receive_idea",
        "retrieve_context",
        "scope_mvp",
        "plan_repo",
        "create_repo",
        "generate_files",
        "commit_progress",
        "verify_build",
        "handle_blocker",
        "verify_build",
        "generate_final_package",
        "remember_outcome",
        "report_result",
    ]
    assert data["agent_steps"] == data["graph_trace"]
    assert all(step["model"] for step in data["agent_steps"])
    assert all(step["decision_trace"] for step in data["agent_steps"])
    model_steps = [step for step in data["agent_steps"] if step["prompt_purpose"]]
    assert {step["prompt_purpose"] for step in model_steps} == {
        "scope_mvp",
        "plan_repo",
        "file_manifest",
        "blocker_analysis",
        "final_package",
    }
    assert all(step["model_mode"] == "mock" for step in model_steps)
    assert "fake-nvidia-key" not in response.text


def test_task_detail_returns_404_for_missing_tasks(client):
    response = client.get(f"/agent/tasks/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_approve_rejects_invalid_decisions(client):
    response = client.post(
        "/agent/approve",
        json={
            "task_id": str(uuid4()),
            "approval_id": str(uuid4()),
            "decision": "maybe",
            "approved_by": "demo_judge",
        },
    )

    assert response.status_code == 422


def test_approve_returns_404_for_unknown_approvals(client):
    task_id = start_task(client)

    response = client.post(
        "/agent/approve",
        json={
            "task_id": task_id,
            "approval_id": str(uuid4()),
            "decision": "approved",
            "approved_by": "demo_judge",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Approval not found"


def test_approve_updates_seeded_pending_approval(app, client):
    task_id = start_task(client)
    approval = asyncio.run(
        app.state.task_store.seed_pending_approval(
            task_id=task_id,
            proposed_action="Post a referral status update",
            risk_level="medium",
        )
    )

    response = client.post(
        "/agent/approve",
        json={
            "task_id": task_id,
            "approval_id": approval.approval_id,
            "decision": "approved",
            "approved_by": "demo_judge",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "task_id": task_id,
        "approval_id": approval.approval_id,
        "status": "approved",
        "approved_by": "demo_judge",
    }

    detail_response = client.get(f"/agent/tasks/{task_id}")
    stored_approval = detail_response.json()["approvals"][0]
    assert stored_approval["status"] == "approved"
    assert stored_approval["approved_by"] == "demo_judge"
    assert stored_approval["resolved_at"] is not None
