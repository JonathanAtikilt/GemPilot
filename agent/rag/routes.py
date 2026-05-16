from fastapi import APIRouter, HTTPException

from agent.rag.build_context import build_build_context_response
from agent.rag.errors import RagConfigurationError
from agent.rag.ingest import ingest_rag
from agent.rag.retrieve import search_rag
from agent.rag.store import get_rag_store
from agent.rag.types import (
    AnswerContextRequest,
    AnswerContextResponse,
    ApiChunk,
    BuildContextRequest,
    BuildContextResponse,
    IngestResponse,
    SearchRequest,
    SearchResponse,
    SourcesResponse,
)

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest() -> IngestResponse:
    try:
        return await ingest_rag()
    except RagConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    try:
        chunks, warning = await search_rag(request.query, request.topK, request.docTypes)
        return SearchResponse(
            query=request.query,
            chunks=[ApiChunk.from_search_result(chunk) for chunk in chunks],
            warning=warning,
        )
    except RagConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/get-build-context", response_model=BuildContextResponse)
async def get_build_context_endpoint(request: BuildContextRequest) -> BuildContextResponse:
    try:
        return await build_build_context_response(request)
    except RagConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/answer-context", response_model=AnswerContextResponse)
async def answer_context(request: AnswerContextRequest) -> AnswerContextResponse:
    try:
        chunks, warning = await search_rag(request.query, request.topK)
        api_chunks = [ApiChunk.from_search_result(chunk) for chunk in chunks]
        return AnswerContextResponse(
            task=request.task,
            query=request.query,
            context=api_chunks,
            recommended_context_summary=_summarize_context(api_chunks),
            warning=warning,
        )
    except RagConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/reindex-logs", response_model=IngestResponse)
async def reindex_logs() -> IngestResponse:
    try:
        return await ingest_rag(logs_only=True)
    except RagConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/sources", response_model=SourcesResponse)
async def sources() -> SourcesResponse:
    try:
        return SourcesResponse(sources=await get_rag_store().list_sources())
    except RagConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


def _summarize_context(chunks: list[ApiChunk]) -> str:
    if not chunks:
        return "No relevant RAG context was found. The orchestrator should proceed cautiously and request more documentation if needed."

    doc_types = ", ".join(sorted({chunk.doc_type for chunk in chunks}))
    sources = ", ".join(dict.fromkeys(chunk.source for chunk in chunks).keys())
    return (
        f"Retrieved {len(chunks)} context chunks from {doc_types}. "
        f"Key sources: {sources}. Use these as grounding evidence for requirements, "
        "constraints, and next-step recommendations, not as the final project decision."
    )
