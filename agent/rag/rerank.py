from agent.rag.types import RagSearchResult


async def rerank_chunks(query: str, chunks: list[RagSearchResult]) -> list[RagSearchResult]:
    """Local rerank placeholder.

    External reranking is intentionally disabled. Vector search already returns cosine
    similarity boosted by source authority; this function keeps a small abstraction for
    future cross-encoder rerankers without requiring another API key today.
    """

    del query
    return sorted(chunks, key=lambda chunk: chunk.score, reverse=True)
