from agent.rag.authority import DOC_TYPE_AUTHORITY, authority_score_for_doc_type
from agent.rag.chunk import chunk_document, detect_doc_type
from agent.rag.types import SourceDocument


def test_authority_scores_match_source_priority() -> None:
    assert authority_score_for_doc_type("hackathon_rules") == 1.0
    assert authority_score_for_doc_type("nvidia_docs") == 0.95
    assert authority_score_for_doc_type("generated_project_doc") == 0.85
    assert authority_score_for_doc_type("build_log") == 0.75
    assert authority_score_for_doc_type("team_notes") == 0.5
    assert authority_score_for_doc_type("unknown") == 0.5
    assert DOC_TYPE_AUTHORITY["hackathon_rules"] > DOC_TYPE_AUTHORITY["build_log"]


def test_chunk_document_sets_authority_from_doc_type() -> None:
    document = SourceDocument(
        source="rag/sources/hackathon_rules.md",
        title="Rules",
        doc_type=detect_doc_type("rag/sources/hackathon_rules.md"),
        text="# Rules\n\nShip the demo.",
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0].authority_score == 1.0
