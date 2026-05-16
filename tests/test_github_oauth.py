from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
import respx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from httpx import Response

from agent.config import Settings
from agent.github_oauth import GitHubConnectionService, InMemoryGitHubConnectionStore
from agent.main import create_app


def github_settings() -> Settings:
    return Settings(
        _env_file=None,
        adapter_mode="mock",
        cors_origins=["http://localhost:3000"],
        frontend_base_url="http://localhost:3000",
        github_oauth_client_id="client-id",
        github_oauth_client_secret="client-secret",
        github_oauth_redirect_uri="http://127.0.0.1:3001/api/auth/github/callback",
        github_token_encryption_key=Fernet.generate_key().decode("utf-8"),
    )


def test_github_connect_redirects_to_github_with_backend_state():
    app = create_app(settings=github_settings())

    with TestClient(app) as client:
        response = client.get(
            "/github/connect?return_to=http://localhost:3000",
            follow_redirects=False,
        )

    assert response.status_code in {302, 307}
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://github.com/login/oauth/authorize"
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["http://127.0.0.1:3001/api/auth/github/callback"]
    assert query["scope"] == ["repo read:user user:email"]
    assert query["state"][0]
    assert "client-secret" not in location


def test_github_connect_redirects_to_frontend_when_oauth_is_not_configured():
    app = create_app(
        settings=Settings(
            _env_file=None,
            adapter_mode="mock",
            cors_origins=["http://localhost:3000"],
            frontend_base_url="http://localhost:3000",
        )
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/auth/github/login?return_to=http://localhost:3000",
            follow_redirects=False,
        )

    assert response.status_code in {302, 307}
    location = response.headers["location"]
    assert location.startswith("http://localhost:3000")
    assert "github_status=error" in location
    assert "GitHub+OAuth+is+not+configured" in location


def test_github_connect_rejects_untrusted_return_to():
    app = create_app(settings=github_settings())

    with TestClient(app) as client:
        response = client.get(
            "/github/connect?return_to=https://evil.example",
            follow_redirects=False,
        )

    assert response.status_code in {302, 307}
    location = response.headers["location"]
    assert location.startswith("http://localhost:3000")
    assert "github_status=error" in location
    assert "Invalid+GitHub+OAuth+return+URL" in location


def test_github_callback_requires_known_state():
    app = create_app(settings=github_settings())

    with TestClient(app) as client:
        response = client.get(
            "/github/callback?code=raw-oauth-code&state=wrong&return_to=http://localhost:3000",
            follow_redirects=False,
        )

    assert response.status_code in {302, 307}
    location = response.headers["location"]
    assert location.startswith("http://localhost:3000")
    assert "github_status=error" in location
    assert "raw-oauth-code" not in location


def test_github_callback_stores_encrypted_code_and_redirects_safely():
    app = create_app(settings=github_settings())

    with TestClient(app) as client:
        connect_response = client.get(
            "/github/connect?return_to=http://localhost:3000",
            follow_redirects=False,
        )
        state = parse_qs(urlparse(connect_response.headers["location"]).query)["state"][0]

        callback_response = client.get(
            f"/github/callback?code=raw-oauth-code&state={state}",
            follow_redirects=False,
        )

    assert callback_response.status_code in {302, 307}
    assert "raw-oauth-code" not in callback_response.text
    assert "raw-oauth-code" not in callback_response.headers["location"]

    callback_query = parse_qs(urlparse(callback_response.headers["location"]).query)
    connection_id = callback_query["github_connection_id"][0]
    assert callback_query["github_status"] == ["ready"]

    record = app.state.github_connection_store.get_connection(connection_id)
    assert record.status == "ready"
    assert record.encrypted_pending_code
    assert record.encrypted_pending_code != "raw-oauth-code"
    assert record.encrypted_access_token is None
    assert app.state.github_connection_service.decrypt_pending_code(record) == "raw-oauth-code"


@pytest.mark.asyncio
@respx.mock
async def test_exchange_ready_connection_stores_token_and_clears_pending_code():
    settings = github_settings()
    store = InMemoryGitHubConnectionStore()
    service = GitHubConnectionService(settings=settings, store=store)
    pending = service.create_pending_connection("http://localhost:3000")
    ready = service.complete_callback(code="raw-oauth-code", state=pending.state)

    respx.post("https://github.com/login/oauth/access_token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "gho-task-token",
                "scope": "repo,read:user,user:email",
                "token_type": "bearer",
            },
        )
    )
    respx.get("https://api.github.com/user").mock(
        return_value=Response(200, json={"login": "octocat", "id": 12345})
    )

    auth = await service.exchange_for_workflow(ready.id, task_id="task-123")

    assert auth.login == "octocat"
    assert auth.config.token == "gho-task-token"
    assert auth.config.owner == "octocat"
    record = store.get_connection(ready.id)
    assert record.task_id == "task-123"
    assert record.status == "exchanged"
    assert record.encrypted_pending_code is None
    assert record.encrypted_access_token
    assert record.encrypted_access_token != "gho-task-token"
    assert record.github_login == "octocat"
    assert record.github_user_id == 12345
