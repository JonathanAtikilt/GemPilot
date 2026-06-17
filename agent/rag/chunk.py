import hashlib
import re
from pathlib import Path

from agent.rag.authority import authority_score_for_doc_type
from agent.rag.types import DocType, RagChunk, SourceDocument

TARGET_CHARS = 2800
OVERLAP_CHARS = 600

SECTION_DOC_TYPE_MAP: dict[str, DocType] = {
    "required deliverables": "required_deliverables",
    "allowed tools and apis": "allowed_tools_apis",
    "required repository format": "repository_format",
    "required demo format": "demo_format",
    "required tech stack pieces": "tech_stack",
    "security constraints": "security_constraints",
    "agent boundaries": "agent_boundaries",
    "scope warnings": "scope_warning",
}


def detect_doc_type_from_section_heading(heading: str) -> DocType | None:
    normalized = re.sub(r"^#{1,6}\s*", "", heading).strip().lower()
    return SECTION_DOC_TYPE_MAP.get(normalized)


def detect_doc_type(source: str) -> DocType:
    name = source.lower()

    if name.startswith("http://") or name.startswith("https://"):
        if "shortesthack" in name or "hackathon" in name:
            return "hackathon_rules"
        if any(provider in name for provider in ("ai.google.dev", "cloud.google.com/vertex-ai", "console.groq.com", "platform.openai.com")):
            return "ai_provider_docs"
        return "generated_project_doc"

    if "hackathon" in name or "rules" in name:
        return "hackathon_rules"
    if any(provider in name for provider in ("gemini", "groq", "openai", "llm_provider", "provider_models")):
        return "ai_provider_docs"
    if "team" in name or "notes" in name:
        return "team_notes"
    if "build_log" in name or "/logs/" in name or name.startswith("logs/"):
        return "build_log"
    if "readme" in name or "docs" in name:
        return "generated_project_doc"
    if "build_requirements" in name or "architecture" in name:
        return "implementation_constraints"
    if "agent" in name:
        return "agent_architecture"

    return "unknown"


def extract_title(text: str, source: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else Path(source).name


def chunk_document(document: SourceDocument) -> list[RagChunk]:
    section_chunks: list[tuple[str, str, DocType | None]] = []
    for heading, body in _split_by_markdown_headings(document.text):
        section_doc_type = detect_doc_type_from_section_heading(heading)
        for text in _split_section(heading, body):
            section_chunks.append((heading, text, section_doc_type))

    chunks: list[RagChunk] = []
    for index, (heading, text, section_doc_type) in enumerate(section_chunks):
        normalized_text = text.strip()
        if not normalized_text:
            continue

        chunk_doc_type = section_doc_type or document.doc_type
        section_heading = _normalize_section_heading(heading)

        digest = hashlib.sha256(
            f"{document.source}:{index}:{normalized_text}".encode("utf-8")
        ).hexdigest()[:24]
        source_slug = re.sub(r"[^a-z0-9]+", "-", Path(document.source).name.lower()).strip("-")

        chunks.append(
            RagChunk(
                chunk_id=f"{source_slug}-{index}-{digest}",
                source=document.source,
                title=document.title,
                doc_type=chunk_doc_type,
                authority_score=authority_score_for_doc_type(chunk_doc_type),
                text=normalized_text,
                metadata={
                    **document.metadata,
                    "source_path": document.source,
                    "section_heading": section_heading,
                    "doc_type": chunk_doc_type,
                    "chunk_index": index,
                    "created_at": document.created_at,
                    "updated_at": document.updated_at,
                },
            )
        )

    return chunks


def _normalize_section_heading(heading: str) -> str | None:
    if not heading:
        return None
    return re.sub(r"^#{1,6}\s*", "", heading).strip() or None


def _split_by_markdown_headings(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    current_heading = ""
    buffer: list[str] = []

    for line in lines:
        is_heading = re.match(r"^#{1,4}\s+", line)
        if is_heading and buffer:
            sections.append((current_heading, "\n".join(buffer)))
            current_heading = line.strip()
            buffer = [line]
            continue

        if is_heading:
            current_heading = line.strip()
        buffer.append(line)

    if buffer:
        sections.append((current_heading, "\n".join(buffer)))

    return sections or [("", text)]


def _split_section(heading: str, body: str) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", body) if paragraph.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        next_text = f"{current}\n\n{paragraph}" if current else paragraph

        if len(next_text) <= TARGET_CHARS:
            current = next_text
            continue

        if current:
            chunks.append(_ensure_heading(heading, current))

        if len(paragraph) > TARGET_CHARS:
            chunks.extend(_split_long_text(heading, paragraph))
            current = ""
        else:
            current = f"{_overlap_tail(current)}{paragraph}"

    if current:
        chunks.append(_ensure_heading(heading, current))

    return chunks


def _split_long_text(heading: str, text: str) -> list[str]:
    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + TARGET_CHARS, len(text))
        chunks.append(_ensure_heading(heading, text[start:end]))
        if end >= len(text):
            break
        start = max(end - OVERLAP_CHARS, start + 1)

    return chunks


def _ensure_heading(heading: str, text: str) -> str:
    if not heading or text.startswith(heading):
        return text
    return f"{heading}\n\n{text}"


def _overlap_tail(text: str) -> str:
    return f"{text[-OVERLAP_CHARS:]}\n\n" if text else ""
