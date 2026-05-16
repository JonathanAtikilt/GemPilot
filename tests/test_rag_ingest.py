from pathlib import Path

import pytest

from agent.rag import ingest as ingest_module
from agent.rag.ingest import load_documents


@pytest.mark.asyncio
async def test_load_documents_reads_sources_and_logs(tmp_path, monkeypatch) -> None:
    sources_dir = tmp_path / "rag" / "sources"
    logs_dir = tmp_path / "logs"
    sources_dir.mkdir(parents=True)
    logs_dir.mkdir()
    (sources_dir / "hackathon_rules.md").write_text("# Rules\n\nBuild the smallest demo.", encoding="utf-8")
    (logs_dir / "build_log.md").write_text("# Build Log\n\nTests passed.", encoding="utf-8")

    monkeypatch.setattr(ingest_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ingest_module, "RAG_SOURCES_DIR", sources_dir)
    monkeypatch.setattr(ingest_module, "LOGS_DIR", logs_dir)

    documents = await load_documents()

    assert sorted(document.source for document in documents) == [
        "logs/build_log.md",
        "rag/sources/hackathon_rules.md",
    ]
    assert {document.doc_type for document in documents} == {"build_log", "hackathon_rules"}
    assert all(document.created_at for document in documents)
    assert all(document.updated_at for document in documents)


@pytest.mark.asyncio
async def test_load_documents_logs_only(tmp_path, monkeypatch) -> None:
    sources_dir = tmp_path / "rag" / "sources"
    logs_dir = tmp_path / "logs"
    sources_dir.mkdir(parents=True)
    logs_dir.mkdir()
    (sources_dir / "team_notes.md").write_text("# Team Notes\n\nUse RAG.", encoding="utf-8")
    (logs_dir / "build_log.md").write_text("# Build Log\n\nFailed once.", encoding="utf-8")

    monkeypatch.setattr(ingest_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ingest_module, "RAG_SOURCES_DIR", sources_dir)
    monkeypatch.setattr(ingest_module, "LOGS_DIR", logs_dir)

    documents = await load_documents(logs_only=True)

    assert len(documents) == 1
    assert documents[0].source == "logs/build_log.md"
    assert documents[0].doc_type == "build_log"


def test_find_text_files_ignores_missing_directories(tmp_path) -> None:
    assert ingest_module._find_text_files(Path(tmp_path / "missing")) == []
