import asyncio
from uuid import UUID, uuid4


VALID_IDEA = (
    "Build a healthcare referral coordination agent that helps clinics "
    "prevent failed referrals."
)


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


def test_task_detail_returns_dashboard_shape_with_initial_graph_trace(client):
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
    assert data["task"]["status"] == "started"
    assert data["retrieved_docs"] == []
    assert data["memory_matches"] == []
    assert data["tool_calls"] == []
    assert data["approvals"] == []
    assert data["generated_artifacts"] == []
    assert data["final_report"] is None
    assert data["agent_steps"][0]["node_name"] == "receive_idea"
    assert data["graph_trace"][0]["node_name"] == "receive_idea"
    assert data["agent_steps"][0]["decision_trace"]


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
