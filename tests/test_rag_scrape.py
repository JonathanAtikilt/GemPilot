import httpx
import pytest
import respx

from agent.rag import scrape as scrape_module
from agent.rag.scrape import (
    collect_same_domain_links,
    normalize_page_url,
    scrape_configured_urls,
    scrape_seed_page,
)


SEED_HTML = """
<html>
  <head><title>Hackathon Rules</title></head>
  <body>
    <main>
      <h1>Rules</h1>
      <p>Build the smallest working demo for judges.</p>
      <a href="/rules/details">Details</a>
      <a href="https://other.example.com/external">External</a>
      <a href="#section">Skip fragment only</a>
      <a href="mailto:team@example.com">Skip mailto</a>
    </main>
  </body>
</html>
"""

DETAILS_HTML = """
<html>
  <head><title>Rule Details</title></head>
  <body>
    <p>Submission deadline and judging criteria for the hackathon demo.</p>
    <p>Teams must show a working MVP, document architecture decisions, and cite NVIDIA model usage.</p>
  </body>
</html>
"""

DEEP_HTML = """
<html><body><p>This page is linked from details but must not be fetched in first-level mode.</p></body></html>
"""


@pytest.mark.asyncio
@respx.mock
async def test_scrape_seed_and_same_domain_first_level_links_only(monkeypatch) -> None:
    seed = "https://hackathon.example.com/rules"
    details = "https://hackathon.example.com/rules/details"
    deep = "https://hackathon.example.com/rules/deep"

    html_headers = {"content-type": "text/html; charset=utf-8"}
    respx.get(seed).mock(return_value=httpx.Response(200, text=SEED_HTML, headers=html_headers))
    respx.get(details).mock(return_value=httpx.Response(200, text=DETAILS_HTML, headers=html_headers))
    respx.get(deep).mock(return_value=httpx.Response(200, text=DEEP_HTML, headers=html_headers))
    respx.get("https://other.example.com/external").mock(
        return_value=httpx.Response(
            200,
            text="<html><body><p>External</p></body></html>",
            headers=html_headers,
        )
    )

    async with httpx.AsyncClient() as client:
        documents = await scrape_seed_page(client, seed)

    sources = {document.source for document in documents}
    assert seed in sources
    assert details in sources
    assert deep not in sources
    assert "https://other.example.com/external" not in sources
    assert respx.calls.call_count == 2

    seed_doc = next(document for document in documents if document.source == seed)
    details_doc = next(document for document in documents if document.source == details)
    assert seed_doc.metadata["link_depth"] == 0
    assert details_doc.metadata["link_depth"] == 1
    assert seed_doc.metadata["origin"] == "web"
    assert seed_doc.doc_type == "hackathon_rules"


def test_collect_same_domain_links_resolves_relative_paths() -> None:
    seed = "https://docs.example.com/start"
    links = collect_same_domain_links(
        seed,
        ["/page-a", "https://docs.example.com/page-b", "https://other.example.com/nope", "#frag"],
    )

    assert links == [
        "https://docs.example.com/page-a",
        "https://docs.example.com/page-b",
    ]


def test_normalize_page_url_rejects_non_html_assets() -> None:
    assert normalize_page_url("https://docs.example.com/guide.pdf") is None
    assert normalize_page_url("not-a-url") is None


@pytest.mark.asyncio
async def test_scrape_configured_urls_reads_env_and_file(monkeypatch, tmp_path) -> None:
    from agent.rag import config as rag_config
    from agent.rag.types import SourceDocument

    scrape_file = tmp_path / "scrape_urls.txt"
    scrape_file.write_text("# comment\nhttps://hackathon.example.com/rules\n", encoding="utf-8")

    monkeypatch.setenv("RAG_SCRAPE_URLS", "https://nvidia.example.com/models,")
    monkeypatch.setattr(rag_config, "RAG_SCRAPE_URLS_FILE", scrape_file)

    async def fake_scrape_seed_page(client, seed_url: str) -> list[SourceDocument]:
        return [
            SourceDocument(
                source=seed_url,
                title="Title",
                doc_type="unknown",
                text="x" * 100,
                metadata={"origin": "web"},
            )
        ]

    monkeypatch.setattr(scrape_module, "scrape_seed_page", fake_scrape_seed_page)

    documents = await scrape_configured_urls()

    assert {document.source for document in documents} == {
        "https://nvidia.example.com/models",
        "https://hackathon.example.com/rules",
    }
