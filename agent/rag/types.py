from typing import Any, Literal

from pydantic import BaseModel, Field

DocType = Literal[
    "hackathon_rules",
    "nvidia_docs",
    "team_notes",
    "build_log",
    "generated_project_doc",
    "unknown",
]


class SourceDocument(BaseModel):
    source: str
    title: str
    doc_type: DocType
    text: str
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagChunk(BaseModel):
    chunk_id: str
    source: str
    title: str
    doc_type: DocType
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class RagSearchResult(RagChunk):
    score: float
    rerank_score: float | None = None


class RagSourceSummary(BaseModel):
    source: str
    doc_type: DocType
    chunk_count: int


class IngestResponse(BaseModel):
    success: bool
    documentsLoaded: int
    chunksCreated: int
    storedIn: Literal["supabase"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    topK: int = Field(default=5, ge=1, le=25)
    docTypes: list[DocType] | None = None


class ApiChunk(BaseModel):
    source: str
    title: str
    doc_type: DocType
    text: str
    score: float

    @classmethod
    def from_search_result(cls, chunk: RagSearchResult) -> "ApiChunk":
        return cls(
            source=chunk.source,
            title=chunk.title,
            doc_type=chunk.doc_type,
            text=chunk.text,
            score=chunk.score,
        )


class SearchResponse(BaseModel):
    query: str
    chunks: list[ApiChunk]
    warning: str | None = None


class AnswerContextRequest(BaseModel):
    task: str = Field(min_length=1)
    query: str = Field(min_length=1)
    topK: int = Field(default=5, ge=1, le=25)


class AnswerContextResponse(BaseModel):
    task: str
    query: str
    context: list[ApiChunk]
    recommended_context_summary: str
    warning: str | None = None


class SourcesResponse(BaseModel):
    sources: list[RagSourceSummary]
