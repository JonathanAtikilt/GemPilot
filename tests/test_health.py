from agent.config import Settings
from agent.main import create_app
from fastapi.testclient import TestClient


def test_health_returns_mock_defaults_without_secret_values(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "status": "ok",
        "adapter_mode": "mock",
        "mock_mode": True,
        "nemotron_model": "nvidia/nemotron-3-super-120b-a12b",
        "nemotron_fast_model": "nvidia/nvidia-nemotron-nano-9b-v2",
        "nvidia_configured": False,
        "openclaw_configured": False,
        "service": "mvpilot-agent",
    }
    assert "NVIDIA_API_KEY" not in response.text
    assert "OPENCLAW_API_KEY" not in response.text


def test_health_is_degraded_when_live_mode_lacks_nvidia_config():
    app = create_app(settings=Settings(_env_file=None, adapter_mode="live"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_settings_load_from_environment_without_requiring_real_keys(monkeypatch):
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nvidia-key")
    monkeypatch.setenv("OPENCLAW_API_KEY", "fake-openclaw-key")
    monkeypatch.setenv("NEMOTRON_MODEL", "nvidia/custom-model")
    monkeypatch.setenv("NEMOTRON_FAST_MODEL", "nvidia/custom-fast-model")
    monkeypatch.setenv("NEMOTRON_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )

    settings = Settings(_env_file=None)

    assert settings.adapter_mode == "live"
    assert settings.nemotron_model == "nvidia/custom-model"
    assert settings.nemotron_fast_model == "nvidia/custom-fast-model"
    assert str(settings.nemotron_base_url) == "https://example.test/v1"
    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    assert settings.nvidia_configured is True
    assert settings.openclaw_configured is True
    assert "fake-nvidia-key" not in settings.model_dump_json()
