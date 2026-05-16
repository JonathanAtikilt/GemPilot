from agent.rag.embed import embed_text
from agent.rag.rerank import rerank_chunks
from agent.rag.store import get_rag_store
from agent.rag.types import DocType, RagSearchResult


async def search_rag(
    query: str,
    top_k: int = 5,
    doc_types: list[DocType] | None = None,
) -> list[RagSearchResult]:
    store = get_rag_store()
    query_embedding = await embed_text(query, input_type="query")
    candidate_count = max(top_k * 3, top_k, 10)
    candidates = await store.search(query_embedding, candidate_count, doc_types)
    try:
        ranked = await rerank_chunks(query, candidates)
    except Exception as exc:
        ranked = [
            candidate.model_copy(
                update={
                    "metadata": {
                        **candidate.metadata,
                        "rerank_warning": f"Rerank unavailable; using vector order ({exc.__class__.__name__}).",
                    }
                }
            )
            for candidate in candidates
        ]
    return ranked[:top_k]
