from __future__ import annotations

import pytest

from agent.rag.config import (
    get_embedding_dimensions,
    get_embedding_model,
    get_embedding_provider,
    get_gemini_api_key,
    get_supabase_service_role_key,
    get_supabase_url,
)
from agent.rag.embed import embed_text
from agent.rag.errors import RagConfigurationError
from agent.rag.rerank import rerank_chunks
from agent.rag.types import RagSearchResult


def test_rag_config_reads_expected_environment(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-embed")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "384")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")

    assert get_gemini_api_key() == "test-gemini"
    assert get_embedding_provider() == "gemini"
    assert get_embedding_model() == "custom-embed"
    assert get_embedding_dimensions() == 384
    assert get_supabase_url() == "https://supabase.test"
    assert get_supabase_service_role_key() == "service-role"


@pytest.mark.asyncio
async def test_embed_text_requires_configured_embedding_key(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RagConfigurationError, match="Missing GEMINI_API_KEY"):
        await embed_text("hello", input_type="query")


@pytest.mark.asyncio
async def test_rerank_chunks_uses_local_score_ordering() -> None:
    chunks = [
        RagSearchResult(
            chunk_id="low",
            source="source.md",
            title="Source",
            doc_type="unknown",
            authority_score=0.5,
            text="lower score",
            score=0.2,
        ),
        RagSearchResult(
            chunk_id="high",
            source="source.md",
            title="Source",
            doc_type="unknown",
            authority_score=0.5,
            text="higher score",
            score=0.9,
        ),
    ]

    reranked = await rerank_chunks("query", chunks)

    assert [chunk.chunk_id for chunk in reranked] == ["high", "low"]
