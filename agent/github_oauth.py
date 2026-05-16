from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, InvalidToken

from agent.config import Settings
from tools.github_tool import GitHubConfig
from tools.policy import repo_prefix


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_OAUTH_SCOPE = "repo read:user user:email"

ConnectionStatus = Literal["pending", "ready", "exchanged", "failed"]


class GitHubOAuthError(Exception):
    """Raised with a safe message for GitHub OAuth failures."""


@dataclass(frozen=True)
class PendingGitHubConnection:
    id: str
    state: str
    authorization_url: str


@dataclass(frozen=True)
class GitHubConnectionRecord:
    id: str
    task_id: str | None
    state_hash: str
    encrypted_pending_code: str | None
    encrypted_access_token: str | None
    scopes: list[str]
    github_login: str | None
    github_user_id: int | None
    status: ConnectionStatus
    return_to: str
    error_summary: str | None
    created_at: datetime
    updated_at: datetime
    exchanged_at: datetime | None


class GitHubConnectionStore(Protocol):
    def create(self, record: GitHubConnectionRecord) -> GitHubConnectionRecord: ...
    def get_connection(self, connection_id: str) -> GitHubConnectionRecord: ...
    def get_by_state_hash(self, state_hash: str) -> GitHubConnectionRecord: ...
    def update(self, record: GitHubConnectionRecord) -> GitHubConnectionRecord: ...
    def delete(self, connection_id: str) -> None: ...


@dataclass(frozen=True)
class GitHubWorkflowAuth:
    connection_id: str
    login: str
    scopes: list[str]
    config: GitHubConfig


class InMemoryGitHubConnectionStore:
    def __init__(self) -> None:
        self._connections: dict[str, GitHubConnectionRecord] = {}

    def create(self, record: GitHubConnectionRecord) -> GitHubConnectionRecord:
        self._connections = {**self._connections, record.id: record}
        return record

    def get_connection(self, connection_id: str) -> GitHubConnectionRecord:
        record = self._connections.get(connection_id)
        if record is None:
            raise GitHubOAuthError("GitHub connection was not found.")
        return record

    def get_by_state_hash(self, state_hash: str) -> GitHubConnectionRecord:
        for record in self._connections.values():
            if record.state_hash == state_hash:
                return record
        raise GitHubOAuthError("Invalid GitHub OAuth state")

    def update(self, record: GitHubConnectionRecord) -> GitHubConnectionRecord:
        if record.id not in self._connections:
            raise GitHubOAuthError("GitHub connection was not found.")
        self._connections = {**self._connections, record.id: record}
        return record

    def delete(self, connection_id: str) -> None:
        self._connections = {
            key: value for key, value in self._connections.items() if key != connection_id
        }


class SupabaseGitHubConnectionStore:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_configured:
            raise GitHubOAuthError("Supabase is not configured for GitHub connections.")
        from supabase import create_client

        secret = settings.supabase_service_role_key
        self._client = create_client(
            settings.supabase_url or "",
            secret.get_secret_value() if secret else "",
        )

    def create(self, record: GitHubConnectionRecord) -> GitHubConnectionRecord:
        response = self._client.table("github_connections").insert(_record_to_row(record)).execute()
        self._raise_for_supabase_error(response, "create GitHub connection")
        return record

    def get_connection(self, connection_id: str) -> GitHubConnectionRecord:
        response = (
            self._client.table("github_connections")
            .select("*")
            .eq("id", connection_id)
            .limit(1)
            .execute()
        )
        self._raise_for_supabase_error(response, "read GitHub connection")
        rows = response.data or []
        if not rows:
            raise GitHubOAuthError("GitHub connection was not found.")
        return _row_to_record(rows[0])

    def get_by_state_hash(self, state_hash: str) -> GitHubConnectionRecord:
        response = (
            self._client.table("github_connections")
            .select("*")
            .eq("state_hash", state_hash)
            .limit(1)
            .execute()
        )
        self._raise_for_supabase_error(response, "read GitHub OAuth state")
        rows = response.data or []
        if not rows:
            raise GitHubOAuthError("Invalid GitHub OAuth state")
        return _row_to_record(rows[0])

    def update(self, record: GitHubConnectionRecord) -> GitHubConnectionRecord:
        response = (
            self._client.table("github_connections")
            .update(_record_to_row(record))
            .eq("id", record.id)
            .execute()
        )
        self._raise_for_supabase_error(response, "update GitHub connection")
        return record

    def delete(self, connection_id: str) -> None:
        response = (
            self._client.table("github_connections")
            .delete()
            .eq("id", connection_id)
            .execute()
        )
        self._raise_for_supabase_error(response, "delete GitHub connection")

    @staticmethod
    def _raise_for_supabase_error(response: object, action: str) -> None:
        error = getattr(response, "error", None)
        if error:
            raise GitHubOAuthError(f"Failed to {action}.")


class GitHubConnectionService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: GitHubConnectionStore,
    ) -> None:
        self._settings = settings
        self._store = store
        self._fernet: Fernet | None = None

    @property
    def store(self) -> GitHubConnectionStore:
        return self._store

    def create_pending_connection(self, return_to: str | None) -> PendingGitHubConnection:
        self._require_oauth_configured()
        safe_return_to = self._validate_return_to(return_to)
        state = secrets.token_urlsafe(32)
        connection_id = str(uuid4())
        now = datetime.now(UTC)
        record = GitHubConnectionRecord(
            id=connection_id,
            task_id=None,
            state_hash=_hash_state(state),
            encrypted_pending_code=None,
            encrypted_access_token=None,
            scopes=[],
            github_login=None,
            github_user_id=None,
            status="pending",
            return_to=safe_return_to,
            error_summary=None,
            created_at=now,
            updated_at=now,
            exchanged_at=None,
        )
        self._store.create(record)
        return PendingGitHubConnection(
            id=connection_id,
            state=state,
            authorization_url=self._authorization_url(state),
        )

    def complete_callback(self, *, code: str, state: str) -> GitHubConnectionRecord:
        self._require_oauth_configured()
        if not code.strip() or not state.strip():
            raise GitHubOAuthError("Invalid GitHub OAuth state")

        record = self._store.get_by_state_hash(_hash_state(state))
        encrypted_code = self._encrypt(code.strip())
        updated = replace(
            record,
            encrypted_pending_code=encrypted_code,
            status="ready",
            updated_at=datetime.now(UTC),
            error_summary=None,
        )
        return self._store.update(updated)

    async def exchange_for_workflow(
        self,
        connection_id: str,
        *,
        task_id: str,
    ) -> GitHubWorkflowAuth:
        self._require_oauth_configured()
        record = self._store.get_connection(connection_id)
        if record.status == "exchanged" and record.encrypted_access_token and record.github_login:
            token = self.decrypt_access_token(record)
            return GitHubWorkflowAuth(
                connection_id=record.id,
                login=record.github_login,
                scopes=list(record.scopes),
                config=_github_config(token, record.github_login),
            )

        if record.status != "ready" or not record.encrypted_pending_code:
            self._mark_failed(record, "GitHub connection is not ready for token exchange.")
            raise GitHubOAuthError("GitHub connection is not ready. Connect GitHub again.")

        code = self.decrypt_pending_code(record)
        try:
            token_payload = await self._exchange_code(code)
            token = str(token_payload.get("access_token") or "").strip()
            if not token:
                raise GitHubOAuthError("GitHub did not return an access token.")
            user_payload = await self._fetch_user(token)
        except GitHubOAuthError as exc:
            self._mark_failed(record, str(exc))
            raise
        except Exception as exc:
            self._mark_failed(record, exc.__class__.__name__)
            raise GitHubOAuthError("GitHub OAuth exchange failed.") from exc

        login = str(user_payload.get("login") or "").strip()
        if not login:
            self._mark_failed(record, "GitHub user response did not include a login.")
            raise GitHubOAuthError("GitHub user response did not include a login.")

        scopes = _parse_scopes(str(token_payload.get("scope") or ""))
        exchanged = replace(
            record,
            task_id=task_id,
            encrypted_pending_code=None,
            encrypted_access_token=self._encrypt(token),
            scopes=scopes,
            github_login=login,
            github_user_id=_safe_int(user_payload.get("id")),
            status="exchanged",
            updated_at=datetime.now(UTC),
            exchanged_at=datetime.now(UTC),
            error_summary=None,
        )
        self._store.update(exchanged)
        return GitHubWorkflowAuth(
            connection_id=connection_id,
            login=login,
            scopes=scopes,
            config=_github_config(token, login),
        )

    def decrypt_pending_code(self, record: GitHubConnectionRecord) -> str:
        if not record.encrypted_pending_code:
            raise GitHubOAuthError("GitHub connection has no pending code.")
        return self._decrypt(record.encrypted_pending_code)

    def decrypt_access_token(self, record: GitHubConnectionRecord) -> str:
        if not record.encrypted_access_token:
            raise GitHubOAuthError("GitHub connection has no access token.")
        return self._decrypt(record.encrypted_access_token)

    def redirect_url_for_completed_callback(self, record: GitHubConnectionRecord) -> str:
        return _append_query(
            record.return_to,
            {
                "github_connection_id": record.id,
                "github_status": "ready",
            },
        )

    def redirect_url_for_error(self, return_to: str | None, message: str) -> str:
        safe_return_to = self._safe_return_to(return_to)
        return _append_query(
            safe_return_to,
            {
                "github_status": "error",
                "github_error": message[:200],
            },
        )

    def create_env_token_connection(self, return_to: str | None) -> GitHubConnectionRecord:
        """Dev fallback when OAuth app vars are missing but GITHUB_TOKEN is configured."""
        if not self._settings.github_pat_configured:
            raise GitHubOAuthError(
                "Backend GitHub token is not configured. Set GITHUB_TOKEN and GITHUB_OWNER."
            )
        self._require_encryption_key()
        token = self._settings.github_personal_access_token
        owner = (self._settings.github_owner or "").strip()
        connection_id = str(uuid4())
        now = datetime.now(UTC)
        record = GitHubConnectionRecord(
            id=connection_id,
            task_id=None,
            state_hash=_hash_state(f"env-token:{connection_id}"),
            encrypted_pending_code=None,
            encrypted_access_token=self._encrypt(token.get_secret_value() if token else ""),
            scopes=["repo", "read:user", "user:email"],
            github_login=owner,
            github_user_id=None,
            status="exchanged",
            return_to=self._validate_return_to(return_to),
            error_summary=None,
            created_at=now,
            updated_at=now,
            exchanged_at=now,
        )
        return self._store.create(record)

    def oauth_public_config(self) -> dict[str, object]:
        return {
            "oauthConfigured": self._settings.github_oauth_configured,
            "patConfigured": self._settings.github_pat_configured,
            "redirectUri": self._settings.github_oauth_redirect_uri,
            "missingEnv": self._missing_oauth_env(),
        }

    def _missing_oauth_env(self) -> list[str]:
        missing: list[str] = []
        if not (self._settings.github_oauth_client_id or "").strip():
            missing.append("GITHUB_OAUTH_CLIENT_ID")
        if not Settings._secret_has_value(self._settings.github_oauth_client_secret):
            missing.append("GITHUB_OAUTH_CLIENT_SECRET")
        if not Settings._secret_has_value(self._settings.github_token_encryption_key):
            missing.append("GITHUB_TOKEN_ENCRYPTION_KEY")
        return missing

    def _safe_return_to(self, return_to: str | None) -> str:
        try:
            return self._validate_return_to(return_to)
        except GitHubOAuthError:
            return self._settings.frontend_base_url

    def _require_encryption_key(self) -> None:
        if not Settings._secret_has_value(self._settings.github_token_encryption_key):
            raise GitHubOAuthError(
                "GITHUB_TOKEN_ENCRYPTION_KEY is required to store GitHub credentials."
            )

    def connection_status(self, connection_id: str | None) -> dict[str, object]:
        if not connection_id:
            return {"connected": False, "githubConnectionId": None, "username": None}
        try:
            record = self._store.get_connection(connection_id)
        except GitHubOAuthError:
            return {"connected": False, "githubConnectionId": connection_id, "username": None}
        connected = record.status in {"ready", "exchanged"}
        return {
            "connected": connected,
            "githubConnectionId": record.id,
            "username": record.github_login,
            "status": record.status,
            "scopes": record.scopes if connected else [],
        }

    def disconnect(self, connection_id: str | None) -> dict[str, object]:
        if connection_id:
            self._store.delete(connection_id)
        return {"connected": False, "githubConnectionId": None, "username": None}

    def _authorization_url(self, state: str) -> str:
        client_id = self._settings.github_oauth_client_id or ""
        redirect_uri = self._settings.github_oauth_redirect_uri or ""
        return f"{GITHUB_AUTHORIZE_URL}?{urlencode({
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': GITHUB_OAUTH_SCOPE,
            'state': state,
        })}"

    async def _exchange_code(self, code: str) -> dict[str, object]:
        secret = self._settings.github_oauth_client_secret
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._settings.github_oauth_client_id,
                    "client_secret": secret.get_secret_value() if secret else "",
                    "code": code,
                    "redirect_uri": self._settings.github_oauth_redirect_uri,
                },
            )
        if response.status_code >= 400:
            raise GitHubOAuthError("GitHub token exchange was rejected.")
        payload = response.json()
        if payload.get("error"):
            raise GitHubOAuthError("GitHub token exchange was rejected.")
        return payload

    async def _fetch_user(self, token: str) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                GITHUB_USER_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "MVPilot-Agent",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if response.status_code >= 400:
            raise GitHubOAuthError("GitHub user lookup failed.")
        return response.json()

    def _validate_return_to(self, return_to: str | None) -> str:
        candidate = (return_to or self._settings.frontend_base_url or "").strip()
        if not candidate:
            raise GitHubOAuthError("Invalid GitHub OAuth return URL")

        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise GitHubOAuthError("Invalid GitHub OAuth return URL")

        allowed_origins = {
            _origin(url)
            for url in [
                self._settings.frontend_base_url,
                *self._settings.cors_origins,
            ]
            if url
        }
        if _origin(candidate) not in allowed_origins:
            raise GitHubOAuthError("Invalid GitHub OAuth return URL")
        return candidate

    def _require_oauth_configured(self) -> None:
        if not self._settings.github_oauth_configured:
            missing = ", ".join(self._missing_oauth_env()) or "GitHub OAuth env vars"
            raise GitHubOAuthError(
                f"GitHub OAuth is not configured. Set {missing} and register "
                f"{self._settings.github_oauth_redirect_uri} in your GitHub OAuth app."
            )

    def _fernet_cipher(self) -> Fernet:
        if self._fernet is not None:
            return self._fernet
        secret = self._settings.github_token_encryption_key
        key = secret.get_secret_value() if secret else ""
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise GitHubOAuthError("GitHub token encryption key is invalid.") from exc
        return self._fernet

    def _encrypt(self, value: str) -> str:
        return self._fernet_cipher().encrypt(value.encode("utf-8")).decode("utf-8")

    def _decrypt(self, value: str) -> str:
        try:
            return self._fernet_cipher().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise GitHubOAuthError("GitHub connection secret could not be decrypted.") from exc

    def _mark_failed(self, record: GitHubConnectionRecord, message: str) -> None:
        self._store.update(
            replace(
                record,
                status="failed",
                error_summary=message[:500],
                updated_at=datetime.now(UTC),
            )
        )


def _github_config(token: str, owner: str) -> GitHubConfig:
    return GitHubConfig(
        token=token,
        owner=owner,
        repo_prefix=repo_prefix(),
        mock_tools=False,
    )


def _parse_scopes(scope_value: str) -> list[str]:
    return [item.strip() for item in scope_value.replace(",", " ").split() if item.strip()]


def _safe_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _record_to_row(record: GitHubConnectionRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "task_id": record.task_id,
        "state_hash": record.state_hash,
        "encrypted_pending_code": record.encrypted_pending_code,
        "encrypted_access_token": record.encrypted_access_token,
        "scopes": list(record.scopes),
        "github_login": record.github_login,
        "github_user_id": record.github_user_id,
        "status": record.status,
        "return_url": record.return_to,
        "error_summary": record.error_summary,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "exchanged_at": record.exchanged_at.isoformat() if record.exchanged_at else None,
    }


def _row_to_record(row: dict[str, object]) -> GitHubConnectionRecord:
    return GitHubConnectionRecord(
        id=str(row["id"]),
        task_id=str(row["task_id"]) if row.get("task_id") else None,
        state_hash=str(row["state_hash"]),
        encrypted_pending_code=str(row["encrypted_pending_code"]) if row.get("encrypted_pending_code") else None,
        encrypted_access_token=str(row["encrypted_access_token"]) if row.get("encrypted_access_token") else None,
        scopes=[str(scope) for scope in row.get("scopes") or []],
        github_login=str(row["github_login"]) if row.get("github_login") else None,
        github_user_id=_safe_int(row.get("github_user_id")),
        status=_connection_status(row.get("status")),
        return_to=str(row["return_url"]),
        error_summary=str(row["error_summary"]) if row.get("error_summary") else None,
        created_at=_parse_datetime(row.get("created_at")),
        updated_at=_parse_datetime(row.get("updated_at")),
        exchanged_at=_parse_optional_datetime(row.get("exchanged_at")),
    )


def _connection_status(value: object) -> ConnectionStatus:
    status = str(value or "pending")
    if status in {"pending", "ready", "exchanged", "failed"}:
        return status  # type: ignore[return-value]
    return "failed"


def _parse_optional_datetime(value: object) -> datetime | None:
    if not value:
        return None
    return _parse_datetime(value)


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(UTC)


def _hash_state(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _append_query(url: str, params: dict[str, str]) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(params)
    return urlunparse(parsed._replace(query=urlencode(query)))
