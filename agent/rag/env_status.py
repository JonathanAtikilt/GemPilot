from __future__ import annotations

from dataclasses import dataclass

from agent.rag.config import (
    get_embedding_api_key,
    get_embedding_dimensions,
    get_embedding_model,
    get_embedding_provider,
    get_supabase_service_role_key,
    get_supabase_url,
)


@dataclass(frozen=True)
class RagEnvRequirement:
    name: str
    description: str
    required: bool = True


RAG_ENV_REQUIREMENTS: tuple[RagEnvRequirement, ...] = (
    RagEnvRequirement(
        "GEMINI_API_KEY or OPENAI_API_KEY",
        "Embeddings for ingest, search, and memory writes",
    ),
    RagEnvRequirement(
        "SUPABASE_URL",
        "Supabase project URL for rag_chunks and memories tables",
    ),
    RagEnvRequirement(
        "SUPABASE_SERVICE_ROLE_KEY",
        "Backend-only key for RAG storage (never expose to frontend)",
    ),
    RagEnvRequirement(
        "EMBEDDING_MODEL",
        "Embedding model id (defaults to gemini-embedding-001)",
        required=False,
    ),
    RagEnvRequirement(
        "EMBEDDING_DIMENSIONS",
        "Embedding size for pgvector (defaults to 768)",
        required=False,
    ),
    RagEnvRequirement(
        "RAG_SCRAPE_URLS",
        "Comma-separated seed URLs for web scrape during ingest",
        required=False,
    ),
)


def missing_required_rag_env() -> list[str]:
    """Return names of required RAG env vars that are unset."""
    missing: list[str] = []
    if not get_embedding_api_key():
        missing.append(
            "OPENAI_API_KEY" if get_embedding_provider() == "openai" else "GEMINI_API_KEY"
        )
    if not get_supabase_url():
        missing.append("SUPABASE_URL")
    if not get_supabase_service_role_key():
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    return missing


def is_rag_configured() -> bool:
    return not missing_required_rag_env()


def rag_env_status() -> dict[str, object]:
    missing = missing_required_rag_env()
    return {
        "configured": not missing,
        "missing_required": missing,
        "embedding_provider": get_embedding_provider(),
        "embedding_model": get_embedding_model(),
        "embedding_dimensions": get_embedding_dimensions(),
        "optional_documented": [
            req.name for req in RAG_ENV_REQUIREMENTS if not req.required
        ],
    }
