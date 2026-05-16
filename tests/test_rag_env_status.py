from agent.rag.env_status import is_rag_configured, missing_required_rag_env


def test_missing_required_rag_env_lists_all_when_unset(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    assert missing_required_rag_env() == [
        "NVIDIA_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    ]
    assert is_rag_configured() is False


def test_is_rag_configured_when_required_vars_present(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")

    assert missing_required_rag_env() == []
    assert is_rag_configured() is True
