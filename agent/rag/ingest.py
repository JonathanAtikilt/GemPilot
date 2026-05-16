from pathlib import Path

from agent.rag.chunk import chunk_document, detect_doc_type, extract_title
from agent.rag.config import LOGS_DIR, PROJECT_ROOT, RAG_SOURCES_DIR, get_embedding_model
from agent.rag.embed import embed_text
from agent.rag.scrape import scrape_configured_urls
from agent.rag.store import get_rag_store
from agent.rag.types import IngestResponse, SourceDocument


async def ingest_rag(logs_only: bool = False) -> IngestResponse:
    store = get_rag_store()
    documents = await load_documents(logs_only=logs_only)
    chunks = [chunk for document in documents for chunk in chunk_document(document)]

    embedded_chunks = []
    for chunk in chunks:
        embedding = await embed_text(chunk.text, input_type="passage")
        chunk.embedding = embedding
        chunk.metadata = {**chunk.metadata, "embedding_model": get_embedding_model()}
        embedded_chunks.append(chunk)

    await store.replace_chunks(embedded_chunks, [document.source for document in documents])

    return IngestResponse(
        success=True,
        documentsLoaded=len(documents),
        chunksCreated=len(embedded_chunks),
        storedIn="supabase",
    )


async def load_documents(logs_only: bool = False) -> list[SourceDocument]:
    documents: list[SourceDocument] = []

    if not logs_only:
        documents.extend(await scrape_configured_urls())

    roots = [LOGS_DIR] if logs_only else [RAG_SOURCES_DIR, LOGS_DIR]
    files = [file_path for root in roots for file_path in _find_text_files(root)]

    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        stat = file_path.stat()
        source = file_path.relative_to(PROJECT_ROOT).as_posix()

        documents.append(
            SourceDocument(
                source=source,
                title=extract_title(text, source),
                doc_type=detect_doc_type(source),
                text=text,
                created_at=_timestamp_iso(stat.st_ctime),
                updated_at=_timestamp_iso(stat.st_mtime),
                metadata={
                    "relative_path": source,
                    "size_bytes": stat.st_size,
                },
            )
        )

    return documents


def _find_text_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        file_path
        for file_path in root.rglob("*")
        if file_path.is_file() and file_path.suffix.lower() in {".md", ".txt"}
    )


def _timestamp_iso(timestamp: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(timestamp, UTC).isoformat()
