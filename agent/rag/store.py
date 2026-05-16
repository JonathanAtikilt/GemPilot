from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agent.rag.authority import authority_score_for_doc_type
from agent.rag.config import get_supabase_service_role_key, get_supabase_url
from agent.rag.errors import RagConfigurationError
from agent.rag.types import DocType, RagChunk, RagSearchResult, RagSourceSummary

if TYPE_CHECKING:
    from supabase import Client


class SupabaseRagStore:
    kind = "supabase"

    def __init__(self) -> None:
        supabase_url = get_supabase_url()
        supabase_key = get_supabase_service_role_key()

        if not supabase_url or not supabase_key:
            raise RagConfigurationError(
                "Supabase is required for RAG storage. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the backend environment."
            )

        from supabase import create_client

        self.client: Client = create_client(supabase_url, supabase_key)

    async def replace_chunks(self, chunks: list[RagChunk], sources: list[str]) -> None:
        if sources:
            delete_response = self.client.table("rag_chunks").delete().in_("source", sources).execute()
            self._raise_for_supabase_error(delete_response, "delete old RAG chunks")

        if not chunks:
            return

        rows = [
            {
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "title": chunk.title,
                "doc_type": chunk.doc_type,
                "authority_score": chunk.authority_score,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "embedding": chunk.embedding,
            }
            for chunk in chunks
        ]

        insert_response = self.client.table("rag_chunks").insert(rows).execute()
        self._raise_for_supabase_error(insert_response, "insert RAG chunks")

    async def search(
        self,
        embedding: list[float],
        top_k: int,
        doc_types: list[DocType] | None = None,
    ) -> list[RagSearchResult]:
        response = self.client.rpc(
            "match_rag_chunks",
            {
                "query_embedding": embedding,
                "match_count": top_k,
                "match_threshold": -1,
                "filter_doc_types": doc_types or None,
            },
        ).execute()
        self._raise_for_supabase_error(response, "search RAG chunks")

        return [
            RagSearchResult(
                chunk_id=str(row["chunk_id"]),
                source=str(row["source"]),
                title=str(row.get("title") or ""),
                doc_type=row.get("doc_type") or "unknown",
                authority_score=float(
                    row.get("authority_score")
                    or authority_score_for_doc_type(row.get("doc_type") or "unknown")
                ),
                text=str(row["text"]),
                metadata=row.get("metadata") or {},
                similarity=float(row.get("similarity") or 0),
                score=float(row.get("weighted_score") or row.get("similarity") or 0),
            )
            for row in response.data or []
        ]

    async def list_sources(self) -> list[RagSourceSummary]:
        response = self.client.table("rag_chunks").select("source, doc_type, authority_score").execute()
        self._raise_for_supabase_error(response, "list RAG sources")
        return _summarize_sources(response.data or [])

    async def write_memory(self, memory: dict[str, Any]) -> None:
        insert_response = self.client.table("memories").insert([memory]).execute()
        self._raise_for_supabase_error(insert_response, "insert memory")

    async def search_memories(self, query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        response = self.client.rpc(
            "match_memories",
            {
                "query_embedding": query_embedding,
                "match_count": top_k,
            },
        ).execute()
        self._raise_for_supabase_error(response, "search memories")
        return response.data or []

    @staticmethod
    def _raise_for_supabase_error(response: Any, action: str) -> None:
        error = getattr(response, "error", None)
        if error:
            raise RuntimeError(f"Failed to {action}: {error}")


def get_rag_store() -> SupabaseRagStore:
    return SupabaseRagStore()


def _summarize_sources(rows: list[dict[str, Any]]) -> list[RagSourceSummary]:
    counts: dict[str, RagSourceSummary] = {}

    for row in rows:
        source = str(row["source"])
        if source in counts:
            counts[source].chunk_count += 1
        else:
            counts[source] = RagSourceSummary(
                source=source,
                doc_type=row.get("doc_type") or "unknown",
                authority_score=float(
                    row.get("authority_score")
                    or authority_score_for_doc_type(row.get("doc_type") or "unknown")
                ),
                chunk_count=1,
            )

    return sorted(counts.values(), key=lambda summary: summary.source)
