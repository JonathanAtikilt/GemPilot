from __future__ import annotations

import json
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        enable_decoding=False,
        extra="ignore",
        populate_by_name=True,
    )

    adapter_mode: Literal["mock", "live"] = Field(
        default="live",
        validation_alias="ADAPTER_MODE",
    )
    allow_idea_aware_partial: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_DEGRADED_MODE", "ALLOW_IDEA_AWARE_PARTIAL"),
    )
    llm_fast_fallback: bool = Field(
        default=False,
        validation_alias="LLM_FAST_FALLBACK",
    )
    llm_live_attempt_timeout_seconds: float = Field(
        default=75,
        gt=0,
        validation_alias="LLM_LIVE_ATTEMPT_TIMEOUT_SECONDS",
    )
    llm_fast_fallback_max_retries: int = Field(
        default=0,
        ge=0,
        validation_alias="LLM_FAST_FALLBACK_MAX_RETRIES",
    )
    llm_fast_fallback_poll_max_seconds: float = Field(
        default=90,
        gt=0,
        validation_alias="LLM_FAST_FALLBACK_POLL_MAX_SECONDS",
    )
    mock_mode_override: bool | None = Field(
        default=None,
        validation_alias="MOCK_MODE",
    )
    llm_provider: Literal["gemini", "groq", "openai"] = Field(
        default="gemini",
        validation_alias="LLM_PROVIDER",
    )
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="GEMINI_API_KEY",
    )
    groq_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="GROQ_API_KEY",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )
    llm_model: str | None = Field(
        default=None,
        validation_alias="LLM_MODEL",
    )
    llm_fallback_model: str | None = Field(
        default=None,
        validation_alias="LLM_FALLBACK_MODEL",
    )
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        validation_alias="GEMINI_BASE_URL",
    )
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias="GROQ_BASE_URL",
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="OPENAI_BASE_URL",
    )
    llm_timeout_seconds: float = Field(
        default=300,
        gt=0,
        validation_alias="LLM_TIMEOUT_SECONDS",
    )
    llm_strict_timeout_seconds: float = Field(
        default=300,
        gt=0,
        validation_alias="LLM_STRICT_TIMEOUT_SECONDS",
    )
    llm_file_manifest_timeout_seconds: float = Field(
        default=600,
        gt=0,
        validation_alias="LLM_FILE_MANIFEST_TIMEOUT_SECONDS",
    )
    llm_repo_plan_timeout_seconds: float = Field(
        default=600,
        gt=0,
        validation_alias="LLM_REPO_PLAN_TIMEOUT_SECONDS",
    )
    llm_max_retries: int = Field(
        default=2,
        ge=0,
        validation_alias="LLM_MAX_RETRIES",
    )
    llm_poll_attempts: int = Field(
        default=1,
        ge=1,
        validation_alias="LLM_POLL_ATTEMPTS",
    )
    llm_poll_interval_seconds: float = Field(
        default=0,
        ge=0,
        validation_alias="LLM_POLL_INTERVAL_SECONDS",
    )
    llm_poll_max_seconds: float = Field(
        default=300,
        gt=0,
        validation_alias="LLM_POLL_MAX_SECONDS",
    )
    llm_file_manifest_poll_max_seconds: float = Field(
        default=600,
        gt=0,
        validation_alias="LLM_FILE_MANIFEST_POLL_MAX_SECONDS",
    )
    llm_repo_plan_poll_max_seconds: float = Field(
        default=600,
        gt=0,
        validation_alias="LLM_REPO_PLAN_POLL_MAX_SECONDS",
    )
    llm_repo_plan_max_retries: int = Field(
        default=3,
        ge=0,
        validation_alias="LLM_REPO_PLAN_MAX_RETRIES",
    )
    llm_reasoning_effort: str = Field(
        default="none",
        validation_alias="LLM_REASONING_EFFORT",
    )
    llm_planning_max_tokens: int = Field(
        default=2500,
        ge=900,
        validation_alias="LLM_PLANNING_MAX_TOKENS",
    )
    llm_repo_plan_max_tokens: int = Field(
        default=6000,
        ge=2000,
        validation_alias="LLM_REPO_PLAN_MAX_TOKENS",
    )
    llm_stack_recommendation_max_tokens: int = Field(
        default=4000,
        ge=1500,
        validation_alias="LLM_STACK_RECOMMENDATION_MAX_TOKENS",
    )
    llm_file_manifest_max_tokens: int = Field(
        default=3500,
        ge=1200,
        validation_alias="LLM_FILE_MANIFEST_MAX_TOKENS",
    )
    llm_file_manifest_max_retries: int = Field(
        default=3,
        ge=0,
        validation_alias="LLM_FILE_MANIFEST_MAX_RETRIES",
    )
    llm_code_generation_max_tokens: int = Field(
        default=8000,
        ge=2000,
        validation_alias="LLM_CODE_GENERATION_MAX_TOKENS",
        description="Max output tokens per staged code-generation LLM call (DB, backend, frontend, docs).",
    )
    require_live_file_manifest: bool = Field(
        default=True,
        validation_alias="REQUIRE_LIVE_FILE_MANIFEST",
    )
    supabase_url: str | None = Field(
        default=None,
        validation_alias="SUPABASE_URL",
    )
    supabase_service_role_key: SecretStr | None = Field(
        default=None,
        validation_alias="SUPABASE_SERVICE_ROLE_KEY",
    )
    supabase_anon_key: SecretStr | None = Field(
        default=None,
        validation_alias="SUPABASE_ANON_KEY",
    )
    github_oauth_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_OAUTH_CLIENT_ID", "GITHUB_CLIENT_ID"),
    )
    github_oauth_client_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_OAUTH_CLIENT_SECRET", "GITHUB_CLIENT_SECRET"),
    )
    github_oauth_redirect_uri: str | None = Field(
        default="http://127.0.0.1:3001/api/auth/github/callback",
        validation_alias=AliasChoices("GITHUB_OAUTH_REDIRECT_URI", "GITHUB_REDIRECT_URI"),
    )
    github_personal_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="GITHUB_TOKEN",
    )
    github_env_token_fallback_enabled: bool = Field(
        default=False,
        validation_alias="GITHUB_ENV_TOKEN_FALLBACK_ENABLED",
    )
    github_owner: str | None = Field(
        default=None,
        validation_alias="GITHUB_OWNER",
    )
    github_token_encryption_key: SecretStr | None = Field(
        default=None,
        validation_alias="GITHUB_TOKEN_ENCRYPTION_KEY",
    )
    frontend_base_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("FRONTEND_BASE_URL", "APP_BASE_URL"),
    )
    rag_scrape_urls: str = Field(
        default="",
        validation_alias="RAG_SCRAPE_URLS",
    )

    @model_validator(mode="after")
    def apply_mock_mode_override(self) -> "Settings":
        if self.mock_mode_override is not None and "adapter_mode" not in self.model_fields_set:
            self.adapter_mode = "mock" if self.mock_mode_override else "live"
        return self
    cors_origins: list[str] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS),
        validation_alias="CORS_ORIGINS",
    )

    @field_validator(
        "gemini_api_key",
        "groq_api_key",
        "openai_api_key",
        "supabase_service_role_key",
        "supabase_anon_key",
        "github_oauth_client_secret",
        "github_token_encryption_key",
        "github_personal_access_token",
        mode="before",
    )
    @classmethod
    def empty_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if value is None:
            return list(DEFAULT_CORS_ORIGINS)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return list(DEFAULT_CORS_ORIGINS)
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return value

    @property
    def mock_mode(self) -> bool:
        return self.adapter_mode == "mock"

    @property
    def llm_model_name(self) -> str:
        if self.llm_model and self.llm_model.strip():
            return self.llm_model.strip()
        return {
            "gemini": "gemini-2.5-flash",
            "groq": "llama-3.1-8b-instant",
            "openai": "gpt-4.1-mini",
        }[self.llm_provider]

    @property
    def llm_fallback_model_name(self) -> str | None:
        if self.llm_fallback_model and self.llm_fallback_model.strip():
            return self.llm_fallback_model.strip()
        if self.llm_provider != "groq" and self._secret_has_value(self.groq_api_key):
            return "llama-3.1-8b-instant"
        return None

    @property
    def llm_configured(self) -> bool:
        return self._secret_has_value(self.llm_api_key) or (
            self.llm_provider != "groq" and self._secret_has_value(self.groq_api_key)
        )

    @property
    def llm_api_key(self) -> SecretStr | None:
        return {
            "gemini": self.gemini_api_key,
            "groq": self.groq_api_key,
            "openai": self.openai_api_key,
        }[self.llm_provider]

    @property
    def llm_base_url(self) -> str:
        return {
            "gemini": self.gemini_base_url,
            "groq": self.groq_base_url,
            "openai": self.openai_base_url,
        }[self.llm_provider]

    @property
    def llm_missing_api_key_name(self) -> str:
        return {
            "gemini": "GEMINI_API_KEY",
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
        }[self.llm_provider]

    @property
    def llm_fast_fallback_active(self) -> bool:
        return self.allow_idea_aware_partial and self.llm_fast_fallback

    @property
    def llm_strict_live_active(self) -> bool:
        return not self.allow_idea_aware_partial

    @property
    def strict_live_file_generation(self) -> bool:
        """When true, staged file generation must stay on the live LLM path."""
        return not self.mock_mode and self.llm_strict_live_active

    @property
    def workflow_live_manifest_only(self) -> bool:
        """Non-mock workflow runs commit only live model artifacts."""
        return not self.mock_mode and self.require_live_file_manifest

    def llm_read_timeout_seconds(self, purpose: str) -> float:
        if self.llm_fast_fallback_active:
            return self.llm_live_attempt_timeout_seconds
        if purpose == "file_manifest":
            return self.llm_file_manifest_timeout_seconds
        if purpose == "plan_repo":
            return self.llm_repo_plan_timeout_seconds
        if self.llm_strict_live_active:
            return max(self.llm_strict_timeout_seconds, self.llm_timeout_seconds)
        return self.llm_timeout_seconds

    @property
    def llm_effective_timeout_seconds(self) -> float:
        return self.llm_read_timeout_seconds("scope_mvp")

    @property
    def llm_effective_max_retries(self) -> int:
        if self.llm_fast_fallback_active:
            return self.llm_fast_fallback_max_retries
        return self.llm_max_retries

    def llm_max_tokens_for(self, purpose: str) -> int:
        if purpose == "plan_repo":
            return self.llm_repo_plan_max_tokens
        if purpose == "file_manifest":
            return self.llm_file_manifest_max_tokens
        if purpose == "recommend_stack":
            return self.llm_stack_recommendation_max_tokens
        if purpose in (
            "generate_database",
            "generate_backend",
            "generate_frontend",
            "generate_docs",
            "generate_demo_video",
        ):
            return self.llm_code_generation_max_tokens
        return self.llm_planning_max_tokens

    def llm_max_retries_for(self, purpose: str) -> int:
        if purpose == "file_manifest":
            return max(self.llm_effective_max_retries, self.llm_file_manifest_max_retries)
        if purpose == "plan_repo":
            return max(self.llm_effective_max_retries, self.llm_repo_plan_max_retries)
        return self.llm_effective_max_retries

    def llm_poll_max_seconds_for(self, purpose: str) -> float:
        if self.llm_fast_fallback_active:
            return self.llm_fast_fallback_poll_max_seconds
        if purpose == "file_manifest":
            return self.llm_file_manifest_poll_max_seconds
        if purpose == "plan_repo":
            return self.llm_repo_plan_poll_max_seconds
        return self.llm_poll_max_seconds

    @property
    def llm_effective_poll_max_seconds(self) -> float:
        return self.llm_poll_max_seconds_for("scope_mvp")

    @property
    def supabase_configured(self) -> bool:
        return bool((self.supabase_url or "").strip()) and self._secret_has_value(
            self.supabase_service_role_key
        )

    @property
    def github_oauth_configured(self) -> bool:
        return (
            bool((self.github_oauth_client_id or "").strip())
            and bool((self.github_oauth_redirect_uri or "").strip())
            and self._secret_has_value(self.github_oauth_client_secret)
            and self._secret_has_value(self.github_token_encryption_key)
        )

    @property
    def github_pat_configured(self) -> bool:
        return self._secret_has_value(self.github_personal_access_token) and bool(
            (self.github_owner or "").strip()
        )

    @property
    def github_pat_token_type(self) -> str | None:
        if not self._secret_has_value(self.github_personal_access_token):
            return None
        token = self.github_personal_access_token.get_secret_value().strip()
        if token.startswith("github_pat_"):
            return "fine_grained"
        if token.startswith("ghp_"):
            return "classic"
        return "unknown"

    @property
    def github_pat_can_create_repositories(self) -> bool:
        token_type = self.github_pat_token_type
        if token_type == "fine_grained":
            return False
        return self.github_pat_configured and token_type in {"classic", "unknown", None}

    @property
    def rag_live_ready(self) -> bool:
        from agent.rag.env_status import is_rag_configured

        return is_rag_configured()

    @staticmethod
    def _secret_has_value(secret: SecretStr | None) -> bool:
        if secret is None:
            return False
        return bool(secret.get_secret_value().strip())

    @property
    def health_status(self) -> Literal["ok", "degraded"]:
        if self.adapter_mode == "live" and not self.llm_configured:
            return "degraded"
        return "ok"
