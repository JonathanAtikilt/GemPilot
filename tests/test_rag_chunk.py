from agent.rag.chunk import chunk_document, detect_doc_type, extract_title
from agent.rag.types import SourceDocument


def test_detect_doc_type_from_known_sources() -> None:
    assert detect_doc_type("https://www.shortesthack.com/?tab=rules") == "hackathon_rules"
    assert detect_doc_type("https://docs.nvidia.com/nim/") == "nvidia_docs"
    assert detect_doc_type("rag/sources/hackathon_rules.md") == "hackathon_rules"
    assert detect_doc_type("rag/sources/nvidia_models.md") == "nvidia_docs"
    assert detect_doc_type("rag/sources/team_notes.md") == "team_notes"
    assert detect_doc_type("README.md") == "generated_project_doc"
    assert detect_doc_type("logs/build_log.md") == "build_log"
    assert detect_doc_type("misc.txt") == "unknown"


def test_chunk_document_preserves_heading_and_metadata() -> None:
    text = "# Team Notes\n\nThe orchestrator should ask RAG for context before action."
    document = SourceDocument(
        source="rag/sources/team_notes.md",
        title=extract_title(text, "rag/sources/team_notes.md"),
        doc_type="team_notes",
        text=text,
        metadata={"relative_path": "rag/sources/team_notes.md"},
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0].title == "Team Notes"
    assert chunks[0].doc_type == "team_notes"
    assert chunks[0].authority_score == 0.5
    assert chunks[0].text.startswith("# Team Notes")
    assert chunks[0].metadata["chunk_index"] == 0


def test_chunk_document_splits_long_text_with_stable_ids() -> None:
    text = "# Long Doc\n\n" + ("A long paragraph about MVPilot requirements. " * 120)
    document = SourceDocument(
        source="rag/sources/long_doc.md",
        title=extract_title(text, "rag/sources/long_doc.md"),
        doc_type="generated_project_doc",
        text=text,
        metadata={},
    )

    chunks = chunk_document(document)

    assert len(chunks) > 1
    assert all(chunk.chunk_id.startswith("long-doc-md-") for chunk in chunks)
    assert all(chunk.text.startswith("# Long Doc") for chunk in chunks)
