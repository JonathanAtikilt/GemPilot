import hashlib
import re
from pathlib import Path

from agent.rag.types import DocType, RagChunk, SourceDocument

TARGET_CHARS = 2800
OVERLAP_CHARS = 600


def detect_doc_type(source: str) -> DocType:
    name = source.lower()

    if "hackathon" in name or "rules" in name:
        return "hackathon_rules"
    if "nvidia" in name or "nemotron" in name:
        return "nvidia_docs"
    if "team" in name or "notes" in name:
        return "team_notes"
    if "build_log" in name or "/logs/" in name or name.startswith("logs/"):
        return "build_log"
    if "readme" in name or "docs" in name:
        return "generated_project_doc"

    return "unknown"


def extract_title(text: str, source: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else Path(source).name


def chunk_document(document: SourceDocument) -> list[RagChunk]:
    raw_chunks: list[str] = []
    for heading, body in _split_by_markdown_headings(document.text):
        raw_chunks.extend(_split_section(heading, body))

    chunks: list[RagChunk] = []
    for index, text in enumerate(raw_chunks):
        normalized_text = text.strip()
        if not normalized_text:
            continue

        digest = hashlib.sha256(
            f"{document.source}:{index}:{normalized_text}".encode("utf-8")
        ).hexdigest()[:24]
        source_slug = re.sub(r"[^a-z0-9]+", "-", Path(document.source).name.lower()).strip("-")

        chunks.append(
            RagChunk(
                chunk_id=f"{source_slug}-{index}-{digest}",
                source=document.source,
                title=document.title,
                doc_type=document.doc_type,
                text=normalized_text,
                metadata={
                    **document.metadata,
                    "chunk_index": index,
                    "created_at": document.created_at,
                    "updated_at": document.updated_at,
                },
            )
        )

    return chunks


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
