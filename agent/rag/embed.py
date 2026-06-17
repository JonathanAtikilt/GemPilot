import httpx

from agent.rag.config import (
    GEMINI_API_BASE_URL,
    OPENAI_API_BASE_URL,
    get_embedding_api_key,
    get_embedding_dimensions,
    get_embedding_model,
    get_embedding_provider,
)
from agent.rag.errors import RagConfigurationError


async def embed_text(text: str, input_type: str = "passage") -> list[float]:
    provider = get_embedding_provider()
    model = get_embedding_model()
    dimensions = get_embedding_dimensions()
    api_key = get_embedding_api_key()
    if not api_key:
        env_name = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
        raise RagConfigurationError(
            f"Missing {env_name}. Set it on the backend before ingesting or searching RAG documents."
        )

    if provider == "openai":
        return await _embed_openai(text, model=model, dimensions=dimensions, api_key=api_key)
    return await _embed_gemini(
        text,
        model=model,
        dimensions=dimensions,
        api_key=api_key,
        input_type=input_type,
    )


async def _embed_gemini(
    text: str,
    *,
    model: str,
    dimensions: int,
    api_key: str,
    input_type: str,
) -> list[float]:
    url = f"{GEMINI_API_BASE_URL}/models/{model}:embedContent"
    task_type = "RETRIEVAL_QUERY" if input_type == "query" else "RETRIEVAL_DOCUMENT"

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
                "outputDimensionality": dimensions,
            },
        )
    body = _response_body(response)
    if response.is_error:
        detail = _error_detail(body, response.reason_phrase)
        raise RuntimeError(f"Gemini embedding request failed: {detail}")

    embedding = body.get("embedding", {}).get("values")
    if not embedding:
        raise RuntimeError("Gemini embedding response did not include an embedding vector.")
    return [float(value) for value in embedding]


async def _embed_openai(
    text: str,
    *,
    model: str,
    dimensions: int,
    api_key: str,
) -> list[float]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{OPENAI_API_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": [text],
                "model": model,
                "dimensions": dimensions,
                "encoding_format": "float",
            },
        )

    body = _response_body(response)
    if response.is_error:
        detail = _error_detail(body, response.reason_phrase)
        raise RuntimeError(f"OpenAI embedding request failed: {detail}")

    embedding = (body.get("data") or [{}])[0].get("embedding")
    if not embedding:
        raise RuntimeError("OpenAI embedding response did not include an embedding vector.")
    return [float(value) for value in embedding]



def _response_body(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _error_detail(body: dict, default: str) -> str:
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or default)
    if isinstance(error, str):
        return error
    return default
