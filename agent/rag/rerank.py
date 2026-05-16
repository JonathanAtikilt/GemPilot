import httpx

from agent.rag.config import get_nvidia_api_key, get_rerank_model, get_rerank_url, normalize_nvidia_model_id
from agent.rag.types import RagSearchResult


async def rerank_chunks(
    query: str,
    chunks: list[RagSearchResult],
) -> tuple[list[RagSearchResult], str | None]:
    api_key = get_nvidia_api_key()
    if not api_key or not chunks:
        warning = None if api_key else "Reranking skipped because NVIDIA_API_KEY is missing."
        return chunks, warning

    try:
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

        body = response.json()
        if response.is_error:
            detail = body.get("error", {}).get("message") or response.reason_phrase
            return chunks, f"Reranking failed; returning vector order. {detail}"

        rankings = body.get("rankings") or []
        if not rankings:
            return chunks, "Reranking response did not include rankings; returning vector order."

        ranked: list[RagSearchResult] = []
        for ranking in sorted(rankings, key=lambda item: item.get("logit", 0), reverse=True):
            index = ranking.get("index")
            if isinstance(index, int) and 0 <= index < len(chunks):
                chunk = chunks[index].model_copy()
                chunk.rerank_score = float(ranking.get("logit", 0))
                chunk.score = chunk.rerank_score * chunk.authority_score
                ranked.append(chunk)

        return ranked, None
    except Exception as error:
        return chunks, f"Reranking failed; returning vector order. {error}"
