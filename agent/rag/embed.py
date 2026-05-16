import httpx

from agent.rag.config import (
    NVIDIA_EMBEDDING_URL,
    get_embedding_model,
    get_nvidia_api_key,
    normalize_nvidia_model_id,
)
from agent.rag.errors import RagConfigurationError


async def embed_text(text: str, input_type: str = "passage") -> list[float]:
    api_key = get_nvidia_api_key()
    if not api_key:
        raise RagConfigurationError(
            "Missing NVIDIA_API_KEY. Set it on the backend before ingesting or searching RAG documents."
        )

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            NVIDIA_EMBEDDING_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": [text],
                "model": normalize_nvidia_model_id(get_embedding_model()),
                "dimensions": 2048,
                "input_type": input_type,
                "encoding_format": "float",
                "truncate": "END",
            },
        )

    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.is_error:
        detail = body.get("error", {}).get("message") or response.reason_phrase
        raise RuntimeError(f"NVIDIA embedding request failed: {detail}")

    embedding = (body.get("data") or [{}])[0].get("embedding")
    if not embedding:
        raise RuntimeError("NVIDIA embedding response did not include an embedding vector.")

    return embedding
