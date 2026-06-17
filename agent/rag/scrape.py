from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from agent.rag.chunk import detect_doc_type
from agent.rag.config import get_scrape_seed_urls
from agent.rag.types import SourceDocument

MAX_FIRST_LEVEL_LINKS = 50
SCRAPE_TIMEOUT_SECONDS = 30.0
USER_AGENT = "GemPilot-RAG/1.0"
MIN_PAGE_TEXT_CHARS = 80
SKIP_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".zip",
    ".tar",
    ".gz",
    ".mp4",
    ".mp3",
    ".css",
    ".js",
    ".json",
    ".xml",
}


async def scrape_urls(seed_urls: list[str]) -> list[SourceDocument]:
    """Scrape explicit seed URLs (orchestrator intake), same rules as configured scrape."""
    seeds = _normalize_seed_list(seed_urls)
    if not seeds:
        return []

    documents: list[SourceDocument] = []
    async with httpx.AsyncClient(
        timeout=SCRAPE_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for seed_url in seeds:
            documents.extend(await scrape_seed_page(client, seed_url))

    return _dedupe_documents(documents)


async def scrape_configured_urls() -> list[SourceDocument]:
    return await scrape_urls(get_scrape_seed_urls())


def _normalize_seed_list(seed_urls: list[str]) -> list[str]:
    normalized: list[str] = []
    for seed in seed_urls:
        page = normalize_page_url(seed)
        if page and page not in normalized:
            normalized.append(page)
    return normalized


async def scrape_seed_page(client: httpx.AsyncClient, seed_url: str) -> list[SourceDocument]:
    normalized_seed = normalize_page_url(seed_url)
    if not normalized_seed:
        return []

    seed_html = await _fetch_html(client, normalized_seed)
    if seed_html is None:
        return []

    seed_title, seed_text, seed_links = parse_html_page(seed_html, normalized_seed)
    documents: list[SourceDocument] = []

    if len(seed_text) >= MIN_PAGE_TEXT_CHARS:
        documents.append(
            _build_web_document(
                url=normalized_seed,
                title=seed_title,
                text=seed_text,
                seed_url=normalized_seed,
                link_depth=0,
            )
        )

    first_level_urls = collect_same_domain_links(normalized_seed, seed_links)[:MAX_FIRST_LEVEL_LINKS]
    for link_url in first_level_urls:
        if link_url == normalized_seed:
            continue

        html = await _fetch_html(client, link_url)
        if html is None:
            continue

        title, text, _ = parse_html_page(html, link_url)
        if len(text) < MIN_PAGE_TEXT_CHARS:
            continue

        documents.append(
            _build_web_document(
                url=link_url,
                title=title,
                text=text,
                seed_url=normalized_seed,
                link_depth=1,
            )
        )

    return documents


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    content_type = (response.headers.get("content-type") or "").lower()
    non_html_prefixes = (
        "application/json",
        "application/pdf",
        "application/octet-stream",
        "image/",
        "video/",
        "audio/",
    )
    if content_type and any(content_type.startswith(prefix) for prefix in non_html_prefixes):
        return None

    return response.text


def parse_html_page(html: str, page_url: str) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else page_url

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body
    text = (main or soup).get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)

    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        links.append(str(anchor["href"]))

    return title, text, links


def collect_same_domain_links(seed_url: str, hrefs: list[str]) -> list[str]:
    seed_domain = domain_key(seed_url)
    collected: list[str] = []
    seen: set[str] = set()

    for href in hrefs:
        if not href or href.startswith("#"):
            continue

        absolute = normalize_page_url(urljoin(seed_url, href))
        if not absolute or not is_http_url(absolute):
            continue
        if domain_key(absolute) != seed_domain:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        collected.append(absolute)

    return collected


def normalize_page_url(url: str) -> str | None:
    cleaned = url.strip()
    if not cleaned or not is_http_url(cleaned):
        return None

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        return None

    path = parsed.path or "/"
    lowered_path = path.lower()
    if any(lowered_path.endswith(ext) for ext in SKIP_EXTENSIONS):
        return None

    without_fragment = urldefrag(cleaned)[0]
    parsed = urlparse(without_fragment)
    normalized = parsed._replace(path=path, fragment="").geturl()
    return normalized.rstrip("/") if parsed.path not in {"", "/"} else normalized


def is_http_url(url: str) -> bool:
    scheme = urlparse(url).scheme.lower()
    return scheme in {"http", "https"}


def domain_key(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        return netloc[4:]
    return netloc


def _build_web_document(
    *,
    url: str,
    title: str,
    text: str,
    seed_url: str,
    link_depth: int,
) -> SourceDocument:
    fetched_at = datetime.now(UTC).isoformat()
    return SourceDocument(
        source=url,
        title=title,
        doc_type=detect_doc_type(url),
        text=text,
        created_at=fetched_at,
        updated_at=fetched_at,
        metadata={
            "origin": "web",
            "seed_url": seed_url,
            "link_depth": link_depth,
            "fetched_at": fetched_at,
        },
    )


def _dedupe_documents(documents: list[SourceDocument]) -> list[SourceDocument]:
    deduped: dict[str, SourceDocument] = {}
    for document in documents:
        deduped[document.source] = document
    return list(deduped.values())
