from agent.config import Settings
from agent.main import create_app
from fastapi.testclient import TestClient


def test_health_returns_mock_defaults_without_secret_values(monkeypatch):
    for key in (
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "GITHUB_TOKEN",
        "GITHUB_OWNER",
        "GITHUB_OAUTH_CLIENT_ID",
        "GITHUB_OAUTH_CLIENT_SECRET",
        "GITHUB_OAUTH_REDIRECT_URI",
        "GITHUB_CLIENT_ID",
        "GITHUB_CLIENT_SECRET",
        "GITHUB_REDIRECT_URI",
        "GITHUB_TOKEN_ENCRYPTION_KEY",
        "REQUIRE_LIVE_FILE_MANIFEST",
    ):
        monkeypatch.delenv(key, raising=False)
    app = create_app(settings=Settings(_env_file=None, adapter_mode="mock"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["adapter_mode"] == "mock"
    assert data["mock_mode"] is True
    assert data["llm_provider"] == "gemini"
    assert data["llm_model"] == "gemini-2.5-flash"
    assert data["llm_configured"] is False
    assert data["runtime"] == "langgraph"
    assert data["registered_tools"] == []
    assert data["supabase_configured"] is False
    assert data["rag_configured"] is False
    assert data["rag_missing_env"] == [
        "GEMINI_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    ]
    assert data["rag_live_ready"] is False
    assert data["github_oauth_configured"] is False
    assert data["github_pat_configured"] is False
    assert data["github_oauth_redirect_uri"] == (
        "http://127.0.0.1:3001/api/auth/github/callback"
    )
    assert data["service"] == "gempilot-agent"
    assert data["require_live_file_manifest"] is True
    assert "fake-google-ai" not in response.text


def test_health_is_degraded_when_live_mode_lacks_llm_config(monkeypatch):
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    app = create_app(settings=Settings(_env_file=None, adapter_mode="live"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_settings_load_from_environment_without_requiring_real_keys(monkeypatch):
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-google-ai-key")
    monkeypatch.setenv("LLM_MODEL", "gemini-custom-model")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("GEMINI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("LLM_POLL_ATTEMPTS", "4")
    monkeypatch.setenv("LLM_POLL_INTERVAL_SECONDS", "0.5")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )

    settings = Settings(_env_file=None)

    assert settings.adapter_mode == "live"
    assert settings.llm_model_name == "gemini-custom-model"
    assert settings.llm_fallback_model_name == "llama-3.1-8b-instant"
    assert str(settings.gemini_base_url) == "https://example.test/v1"
    assert settings.llm_timeout_seconds == 12
    assert settings.llm_max_retries == 2
    assert settings.llm_poll_attempts == 4
    assert settings.llm_poll_interval_seconds == 0.5
    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    assert settings.llm_configured is True
    assert "fake-google-ai-key" not in settings.model_dump_json()


def test_health_reports_rag_configured_when_supabase_and_gemini_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-google-ai-key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-service-role")

    app = create_app(settings=Settings(_env_file=None, adapter_mode="mock"))

    with TestClient(app) as client:
        response = client.get("/health")

    data = response.json()
    assert data["rag_configured"] is True
    assert data["rag_missing_env"] == []
    assert data["rag_live_ready"] is True
    assert data["supabase_configured"] is True
    assert data["runtime"] == "langgraph"
    assert data["registered_tools"] == []
