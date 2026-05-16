from __future__ import annotations

import json
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
        default="mock",
        validation_alias="ADAPTER_MODE",
    )
    nvidia_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="NVIDIA_API_KEY",
    )
    nemotron_model: str = Field(
        default="nvidia/nemotron-3-super-120b-a12b",
        validation_alias="NEMOTRON_MODEL",
    )
    nemotron_fast_model: str = Field(
        default="nvidia/nvidia-nemotron-nano-9b-v2",
        validation_alias="NEMOTRON_FAST_MODEL",
    )
    nemotron_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        validation_alias="NEMOTRON_BASE_URL",
    )
    nemotron_timeout_seconds: float = Field(
        default=30,
        gt=0,
        validation_alias="NEMOTRON_TIMEOUT_SECONDS",
    )
    nemotron_max_retries: int = Field(
        default=1,
        ge=0,
        validation_alias="NEMOTRON_MAX_RETRIES",
    )
    nemotron_poll_attempts: int = Field(
        default=3,
        ge=1,
        validation_alias="NEMOTRON_POLL_ATTEMPTS",
    )
    nemotron_poll_interval_seconds: float = Field(
        default=1,
        ge=0,
        validation_alias="NEMOTRON_POLL_INTERVAL_SECONDS",
    )
    openclaw_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENCLAW_API_KEY",
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS),
        validation_alias="CORS_ORIGINS",
    )

    @field_validator("nvidia_api_key", "openclaw_api_key", mode="before")
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
    def nvidia_configured(self) -> bool:
        return self._secret_has_value(self.nvidia_api_key)

    @property
    def openclaw_configured(self) -> bool:
        return self._secret_has_value(self.openclaw_api_key)

    @staticmethod
    def _secret_has_value(secret: SecretStr | None) -> bool:
        if secret is None:
            return False
        return bool(secret.get_secret_value().strip())

    @property
    def health_status(self) -> Literal["ok", "degraded"]:
        if self.adapter_mode == "live" and not self.nvidia_configured:
            return "degraded"
        return "ok"
