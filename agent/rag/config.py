import os
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_SOURCES_DIR = PROJECT_ROOT / "rag" / "sources"
LOGS_DIR = PROJECT_ROOT / "logs"

EmbeddingProvider = Literal["gemini", "openai"]

DEFAULT_GEMINI_EMBED_MODEL = "gemini-embedding-001"
DEFAULT_OPENAI_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSIONS = 768
GEMINI_API_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta",
).rstrip("/")
OPENAI_API_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def get_gemini_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY", "").strip() or None


def get_openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY", "").strip() or None


def get_embedding_provider() -> EmbeddingProvider:
    configured = os.getenv("EMBEDDING_PROVIDER", "").strip().lower()
    if configured in {"gemini", "openai"}:
        return configured  # type: ignore[return-value]

    model = os.getenv("EMBEDDING_MODEL", "").strip().lower()
    if model.startswith("text-embedding"):
        return "openai"
    if model.startswith("gemini"):
        return "gemini"

    llm_provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if llm_provider == "openai":
        return "openai"
    return "gemini"


def get_embedding_model() -> str:
    configured = os.getenv("EMBEDDING_MODEL", "").strip()
    if configured:
        return configured
    return (
        DEFAULT_OPENAI_EMBED_MODEL
        if get_embedding_provider() == "openai"
        else DEFAULT_GEMINI_EMBED_MODEL
    )


def get_embedding_dimensions() -> int:
    value = os.getenv("EMBEDDING_DIMENSIONS", "").strip()
    if not value:
        return DEFAULT_EMBEDDING_DIMENSIONS
    return int(value)


def get_embedding_api_key() -> str | None:
    provider = get_embedding_provider()
    if provider == "openai":
        return get_openai_api_key()
    return get_gemini_api_key()


def get_supabase_url() -> str | None:
    return os.getenv("SUPABASE_URL", "").strip() or None


def get_supabase_service_role_key() -> str | None:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or None


RAG_SCRAPE_URLS_FILE = PROJECT_ROOT / "rag" / "scrape_urls.txt"


def get_scrape_seed_urls() -> list[str]:
    urls: list[str] = []

    for part in os.getenv("RAG_SCRAPE_URLS", "").split(","):
        candidate = part.strip()
        if candidate:
            urls.append(candidate)

    if RAG_SCRAPE_URLS_FILE.exists():
        for line in RAG_SCRAPE_URLS_FILE.read_text(encoding="utf-8").splitlines():
            candidate = line.strip()
            if candidate and not candidate.startswith("#"):
                urls.append(candidate)

    return list(dict.fromkeys(urls))
