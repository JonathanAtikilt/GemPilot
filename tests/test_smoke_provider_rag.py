from __future__ import annotations

from agent.rag.types import IngestResponse, RagSearchResult


def test_orchestrator_and_rag_endpoint_smoke(client, mock_live_rag_search, monkeypatch):
    run_response = client.post(
        "/agent/run",
        json={
            "idea": "Build a simple MVP that tracks study goals and weekly review tasks.",
            "repo_visibility": "private",
            "demo_mode": True,
        },
    )

    assert run_response.status_code == 202
    task_id = run_response.json()["task_id"]

    detail_response = client.get(f"/agent/tasks/{task_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert "study goals" in detail["mvp_plan"]["idea"]
    assert detail["build_context"]["evidence"]

    async def fake_ingest_rag(logs_only: bool = False):
        return IngestResponse(
            success=True,
            documentsLoaded=1,
            chunksCreated=1,
            storedIn="supabase",
        )

    async def fake_search_rag(query: str, top_k: int = 5, doc_types=None):
        del doc_types
        return [
            RagSearchResult(
                chunk_id="smoke-0",
                source="rag/sources/smoke.md",
                title="Smoke Test Document",
                doc_type="generated_project_doc",
                authority_score=0.85,
                text=(
                    "# Smoke Test Document\n\n"
                    "- Build the smallest useful MVP first.\n"
                    "- Cite source chunks in planning answers."
                ),
                metadata={"section_heading": "Smoke Test Document"},
                score=0.99,
                similarity=0.99,
            )
        ][:top_k]

    monkeypatch.setattr("agent.rag.routes.ingest_rag", fake_ingest_rag)
    monkeypatch.setattr("agent.rag.routes.search_rag", fake_search_rag)

    ingest_response = client.post("/rag/ingest")
    assert ingest_response.status_code == 200
    assert ingest_response.json()["chunksCreated"] == 1

    search_response = client.post(
        "/rag/search",
        json={"query": "What should the MVP build first?", "topK": 1},
    )
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert search_payload["chunks"][0]["source"] == "rag/sources/smoke.md"

    answer_response = client.post(
        "/rag/answer-context",
        json={
            "task": "Plan a simple MVP",
            "query": "What context matters for the plan?",
            "topK": 1,
        },
    )
    assert answer_response.status_code == 200
    answer_payload = answer_response.json()
    assert answer_payload["task"] == "Plan a simple MVP"
    assert "rag/sources/smoke.md" in answer_payload["recommended_context_summary"]
