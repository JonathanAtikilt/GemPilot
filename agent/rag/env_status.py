from __future__ import annotations

from dataclasses import dataclass

from agent.rag.config import (
    get_nvidia_api_key,
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
        "NVIDIA_API_KEY",
        "Embeddings and reranking for ingest, search, and memory writes",
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
        "NVIDIA_EMBED_MODEL",
        "Embedding model id (defaults to llama-nemotron-embed-1b-v2)",
        required=False,
    ),
    RagEnvRequirement(
        "NVIDIA_RERANK_MODEL",
        "Rerank model id (defaults to llama-nemotron-rerank-1b-v2)",
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
    if not get_nvidia_api_key():
        missing.append("NVIDIA_API_KEY")
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
        "optional_documented": [
            req.name for req in RAG_ENV_REQUIREMENTS if not req.required
        ],
    }
