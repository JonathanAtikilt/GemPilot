from agent.rag.embed import embed_text
from agent.rag.rerank import rerank_chunks
from agent.rag.store import get_rag_store
from agent.rag.types import DocType, RagSearchResult


async def search_rag(
    query: str,
    top_k: int = 5,
    doc_types: list[DocType] | None = None,
) -> tuple[list[RagSearchResult], str | None]:
    store = get_rag_store()
    query_embedding = await embed_text(query, input_type="query")
    candidate_count = max(top_k * 3, top_k, 10)
    candidates = await store.search(query_embedding, candidate_count, doc_types)
    ranked, warning = await rerank_chunks(query, candidates)
    return ranked[:top_k], warning
