import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_SOURCES_DIR = PROJECT_ROOT / "rag" / "sources"
LOGS_DIR = PROJECT_ROOT / "logs"

DEFAULT_NVIDIA_EMBED_MODEL = "llama-nemotron-embed-1b-v2"
DEFAULT_NVIDIA_RERANK_MODEL = "llama-nemotron-rerank-1b-v2"
NVIDIA_EMBEDDING_URL = os.getenv(
    "NVIDIA_EMBEDDING_URL",
    "https://integrate.api.nvidia.com/v1/embeddings",
)


def get_nvidia_api_key() -> str | None:
    return os.getenv("NVIDIA_API_KEY", "").strip() or None


def get_embedding_model() -> str:
    return os.getenv("NVIDIA_EMBED_MODEL", DEFAULT_NVIDIA_EMBED_MODEL).strip()


def get_rerank_model() -> str:
    return os.getenv("NVIDIA_RERANK_MODEL", DEFAULT_NVIDIA_RERANK_MODEL).strip()


def normalize_nvidia_model_id(model: str) -> str:
    return model if "/" in model else f"nvidia/{model}"


def get_rerank_url() -> str:
    model = normalize_nvidia_model_id(get_rerank_model())
    return os.getenv(
        "NVIDIA_RERANK_URL",
        f"https://ai.api.nvidia.com/v1/retrieval/{model}/reranking",
    ).strip()


def get_supabase_url() -> str | None:
    return os.getenv("SUPABASE_URL", "").strip() or None


def get_supabase_service_role_key() -> str | None:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or None
