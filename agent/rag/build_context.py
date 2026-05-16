from __future__ import annotations

import logging
import re
from typing import Any

from agent.rag.chunk import detect_doc_type_from_section_heading
from agent.rag.retrieve import search_rag
from agent.rag.types import (
    BuildContextItem,
    BuildContextOptionalParams,
    BuildContextRequest,
    BuildContextResponse,
    BuildContextResponseCategory,
    DocType,
    EvidenceItem,
    Priority,
    RagSearchResult,
    ScopeWarningItem,
)

logger = logging.getLogger(__name__)

BUILD_CONTEXT_DOC_TYPES: list[DocType] = [
    "required_deliverables",
    "allowed_tools_apis",
    "repository_format",
    "demo_format",
    "tech_stack",
    "scope_warning",
    "hackathon_rules",
    "nvidia_docs",
    "nvidia_model_docs",
    "agent_architecture",
    "implementation_constraints",
    "generated_project_doc",
]

DOC_TYPE_TO_CATEGORY: dict[DocType, BuildContextResponseCategory] = {
    "required_deliverables": "requiredDeliverables",
    "allowed_tools_apis": "allowedToolsAndAPIs",
    "repository_format": "requiredRepositoryFormat",
    "demo_format": "requiredDemoFormat",
    "tech_stack": "requiredTechStackPieces",
    "hackathon_rules": "requiredDeliverables",
    "nvidia_docs": "requiredTechStackPieces",
    "nvidia_model_docs": "requiredTechStackPieces",
    "agent_architecture": "requiredTechStackPieces",
    "implementation_constraints": "scopeWarnings",
    "generated_project_doc": "requiredRepositoryFormat",
    "build_log": "scopeWarnings",
    "team_notes": "scopeWarnings",
    "unknown": "scopeWarnings",
}

WEAK_RETRIEVAL_SCORE_THRESHOLD = 0.15

_FALLBACK_ITEMS: dict[BuildContextResponseCategory, list[str]] = {
    "requiredDeliverables": [
        "Working MVP",
        "GitHub repository",
        "README.md",
        "Setup instructions",
        "Agent activity/build log",
        "Clear NVIDIA/Nemotron usage explanation",
    ],
    "allowedToolsAndAPIs": [
        "NVIDIA API",
        "GitHub API",
        "Supabase",
        "FastAPI",
        "React or Next.js",
        "Supabase pgvector",
    ],
    "requiredRepositoryFormat": [
        "README.md",
        ".env.example",
        "docs/BUILD_LOG.md",
        "docs/ARCHITECTURE.md",
        "frontend/backend or apps/web/apps/api structure",
        "rag/sources",
        "logs",
    ],
    "requiredDemoFormat": [
        "Show user entering project idea",
        "Show RAG retrieving build context",
        "Show Orchestrator generating plan",
        "Show GitHub Agent committing files",
        "Show frontend displaying logs and final repo link",
    ],
    "requiredTechStackPieces": [
        "React or Next.js frontend",
        "FastAPI backend",
        "Supabase Postgres",
        "Supabase pgvector",
        "NVIDIA embedding model",
        "NVIDIA reranker model",
        "Nemotron reasoning model",
        "GitHub API integration",
    ],
}

_CATEGORY_FIELDS: dict[BuildContextResponseCategory, str] = {
    "requiredDeliverables": "requiredDeliverables",
    "allowedToolsAndAPIs": "allowedToolsAndAPIs",
    "requiredRepositoryFormat": "requiredRepositoryFormat",
    "requiredDemoFormat": "requiredDemoFormat",
    "requiredTechStackPieces": "requiredTechStackPieces",
}


async def get_build_context(
    project_id: str,
    idea: str,
    optional_params: BuildContextOptionalParams | dict[str, Any] | None = None,
    *,
    top_k: int = 8,
) -> BuildContextResponse:
    parsed_params: BuildContextOptionalParams | None
    if isinstance(optional_params, dict):
        parsed_params = BuildContextOptionalParams.model_validate(optional_params)
    else:
        parsed_params = optional_params

    request = BuildContextRequest(
        projectId=project_id,
        idea=idea,
        optionalParams=parsed_params,
        topK=top_k,
    )
    return await build_build_context_response(request)


async def build_build_context_response(request: BuildContextRequest) -> BuildContextResponse:
    query = _build_search_query(request)
    chunks, warning = await search_rag(query, request.topK, BUILD_CONTEXT_DOC_TYPES)
    reranked_count = len(chunks)

    categorized = _categorize_chunks(chunks)
    evidence = _build_evidence(chunks)
    used_fallback_categories: list[str] = []
    weak_retrieval = not chunks or max((chunk.score for chunk in chunks), default=0) < WEAK_RETRIEVAL_SCORE_THRESHOLD

    response_items: dict[BuildContextResponseCategory, list[BuildContextItem]] = {
        category: [] for category in _CATEGORY_FIELDS
    }
    scope_warnings: list[ScopeWarningItem] = []

    for category in _CATEGORY_FIELDS:
        extracted = categorized.get(category, [])
        if extracted:
            response_items[category] = extracted
        else:
            response_items[category] = _fallback_items(category)
            used_fallback_categories.append(category)

    for item in categorized.get("scopeWarnings", []):
        scope_warnings.append(
            ScopeWarningItem(item=item.item, reason=item.reason, source=item.source)
        )

    if not scope_warnings:
        scope_warnings = _default_scope_warnings() if weak_retrieval or not chunks else scope_warnings

    logger.info(
        "rag.get_build_context projectId=%s query=%r docTypes=%s chunks=%s reranked=%s "
        "fallbackCategories=%s warning=%s",
        request.projectId,
        query,
        BUILD_CONTEXT_DOC_TYPES,
        len(chunks),
        reranked_count,
        used_fallback_categories,
        warning,
    )

    return BuildContextResponse(
        requiredDeliverables=response_items["requiredDeliverables"],
        allowedToolsAndAPIs=response_items["allowedToolsAndAPIs"],
        requiredRepositoryFormat=response_items["requiredRepositoryFormat"],
        requiredDemoFormat=response_items["requiredDemoFormat"],
        requiredTechStackPieces=response_items["requiredTechStackPieces"],
        scopeWarnings=scope_warnings,
        evidence=evidence,
    )


def _build_search_query(request: BuildContextRequest) -> str:
    parts = [
        request.idea,
        "hackathon required deliverables allowed tools APIs repository format demo format tech stack constraints",
    ]
    params = request.optionalParams
    if params:
        if params.stack:
            parts.append("stack: " + ", ".join(params.stack))
        if params.features:
            parts.append("features: " + ", ".join(params.features))
        if params.repoPreference:
            parts.append(f"repository preference: {params.repoPreference}")
        if params.demoPreference:
            parts.append(f"demo preference: {params.demoPreference}")
    return " ".join(part for part in parts if part).strip()


def _categorize_chunks(chunks: list[RagSearchResult]) -> dict[str, list[BuildContextItem]]:
    buckets: dict[str, list[BuildContextItem]] = {category: [] for category in _CATEGORY_FIELDS}
    buckets["scopeWarnings"] = []
    seen: set[tuple[str, str]] = set()

    for chunk in chunks:
        category = DOC_TYPE_TO_CATEGORY.get(chunk.doc_type, "scopeWarnings")
        if chunk.doc_type == "scope_warning":
            category = "scopeWarnings"

        for bullet in _extract_bullets(chunk.text):
            key = (category, _normalize_item(bullet))
            if key in seen:
                continue
            seen.add(key)

            item = BuildContextItem(
                item=bullet,
                priority=_infer_priority(bullet, chunk),
                reason=_build_reason(chunk),
                source=chunk.source,
            )

            if category == "scopeWarnings":
                buckets["scopeWarnings"].append(item)
            else:
                buckets[category].append(item)

    for category in _CATEGORY_FIELDS:
        buckets[category].sort(key=lambda item: _priority_rank(item.priority), reverse=True)

    return buckets


def _extract_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^[-*]\s+(.+)$", line.strip())
        if match:
            bullets.append(match.group(1).strip())
    if not bullets:
        condensed = re.sub(r"\s+", " ", text).strip()
        if condensed and len(condensed) <= 240:
            bullets.append(condensed)
    return bullets


def _infer_priority(text: str, chunk: RagSearchResult) -> Priority:
    lowered = text.lower()
    if any(word in lowered for word in ("must", "required", "critical", "never", "do not")):
        return "critical"
    if any(word in lowered for word in ("should", "need to", "ensure")):
        return "high"
    if chunk.doc_type in {"hackathon_rules", "required_deliverables", "scope_warning"}:
        return "high"
    if chunk.authority_score >= 0.9:
        return "high"
    if any(word in lowered for word in ("may", "optional", "can")):
        return "low"
    return "medium"


def _build_reason(chunk: RagSearchResult) -> str:
    section = chunk.metadata.get("section_heading")
    if section:
        return f"Grounded in section '{section}' from {chunk.source}."
    return f"Grounded in {chunk.doc_type} documentation from {chunk.source}."


def _build_evidence(chunks: list[RagSearchResult]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            source=chunk.source,
            docType=chunk.doc_type,
            chunkId=chunk.chunk_id,
            content=chunk.text,
            score=chunk.score,
        )
        for chunk in chunks
    ]


def _fallback_items(category: BuildContextResponseCategory) -> list[BuildContextItem]:
    return [
        BuildContextItem(
            item=text,
            priority="high" if category == "requiredDeliverables" else "medium",
            reason="MVPilot default when retrieval is sparse or no matching chunks were found.",
            source="mvpilot://defaults",
        )
        for text in _FALLBACK_ITEMS[category]
    ]


def _default_scope_warnings() -> list[ScopeWarningItem]:
    return [
        ScopeWarningItem(
            item="Do not expose SUPABASE_SERVICE_ROLE_KEY to the frontend",
            reason="MVPilot default scope warning.",
            source="mvpilot://defaults",
        ),
        ScopeWarningItem(
            item="Do not treat raw logs as higher authority than hackathon rules or official model docs",
            reason="MVPilot default scope warning.",
            source="mvpilot://defaults",
        ),
    ]


def _normalize_item(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _priority_rank(priority: Priority) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}[priority]


def default_build_context_response(
    request: BuildContextRequest | None = None,
) -> BuildContextResponse:
    """Deterministic MVPilot defaults for mock mode or when RAG is not configured."""
    _ = request
    return BuildContextResponse(
        requiredDeliverables=_fallback_items("requiredDeliverables"),
        allowedToolsAndAPIs=_fallback_items("allowedToolsAndAPIs"),
        requiredRepositoryFormat=_fallback_items("requiredRepositoryFormat"),
        requiredDemoFormat=_fallback_items("requiredDemoFormat"),
        requiredTechStackPieces=_fallback_items("requiredTechStackPieces"),
        scopeWarnings=_default_scope_warnings(),
        evidence=[],
    )
