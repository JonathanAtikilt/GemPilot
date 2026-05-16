import pytest

from agent.rag.config import (
    get_embedding_model,
    get_nvidia_api_key,
    get_rerank_model,
    get_rerank_url,
    get_supabase_service_role_key,
    get_supabase_url,
    normalize_nvidia_model_id,
)
from agent.rag.embed import embed_text
from agent.rag.errors import RagConfigurationError
from agent.rag.rerank import rerank_chunks
from agent.rag.types import RagSearchResult


def test_rag_config_reads_expected_environment(monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "test-nvidia")
    monkeypatch.setenv("NVIDIA_EMBED_MODEL", "custom-embed")
    monkeypatch.setenv("NVIDIA_RERANK_MODEL", "custom-rerank")
    monkeypatch.setenv("NVIDIA_RERANK_URL", "https://rerank.test")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")

    assert get_nvidia_api_key() == "test-nvidia"
    assert get_embedding_model() == "custom-embed"
    assert get_rerank_model() == "custom-rerank"
    assert get_rerank_url() == "https://rerank.test"
    assert get_supabase_url() == "https://supabase.test"
    assert get_supabase_service_role_key() == "service-role"
    assert normalize_nvidia_model_id("plain-model") == "nvidia/plain-model"
    assert normalize_nvidia_model_id("vendor/model") == "vendor/model"


@pytest.mark.asyncio
async def test_embed_text_requires_nvidia_key(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    with pytest.raises(RagConfigurationError, match="Missing NVIDIA_API_KEY"):
        await embed_text("hello", input_type="query")


@pytest.mark.asyncio
async def test_rerank_chunks_requires_nvidia_key(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    chunks = [
        RagSearchResult(
            chunk_id="chunk-1",
            source="source.md",
            title="Source",
            doc_type="unknown",
            authority_score=0.5,
            text="first chunk",
            score=0.7,
        )
    ]

    with pytest.raises(RagConfigurationError, match="Missing NVIDIA_API_KEY"):
        await rerank_chunks("query", chunks)
