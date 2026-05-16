import httpx

from agent.rag.config import get_nvidia_api_key, get_rerank_model, get_rerank_url, normalize_nvidia_model_id
from agent.rag.errors import RagConfigurationError
from agent.rag.types import RagSearchResult


async def rerank_chunks(query: str, chunks: list[RagSearchResult]) -> list[RagSearchResult]:
    if not chunks:
        return []

    api_key = get_nvidia_api_key()
    if not api_key:
        raise RagConfigurationError(
            "Missing NVIDIA_API_KEY. Set it on the backend before reranking RAG results."
        )

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            get_rerank_url(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": normalize_nvidia_model_id(get_rerank_model()),
                "query": {"text": query},
                "passages": [{"text": chunk.text} for chunk in chunks],
                "truncate": "END",
            },
        )

    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.is_error:
        detail = body.get("error", {}).get("message") or response.reason_phrase
        raise RuntimeError(f"NVIDIA rerank request failed: {detail}")

    rankings = body.get("rankings") or []
    if not rankings:
        raise RuntimeError("NVIDIA rerank response did not include rankings.")

    ranked: list[RagSearchResult] = []
    for ranking in sorted(rankings, key=lambda item: item.get("logit", 0), reverse=True):
        index = ranking.get("index")
        if isinstance(index, int) and 0 <= index < len(chunks):
            chunk = chunks[index].model_copy()
            chunk.rerank_score = float(ranking.get("logit", 0))
            chunk.score = chunk.rerank_score * chunk.authority_score
            ranked.append(chunk)

    return ranked
