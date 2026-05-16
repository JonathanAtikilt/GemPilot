def test_sources_requires_supabase(monkeypatch, client) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    response = client.get("/rag/sources")

    assert response.status_code == 503
    assert "Supabase is required" in response.json()["detail"]
