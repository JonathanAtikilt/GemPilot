from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from agent.rag.scrape import normalize_page_url


def _canonicalize_url(url: str) -> str | None:
    page = normalize_page_url(url)
    if not page:
        return None
    parsed = urlparse(page)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return urlunparse(parsed._replace(netloc=netloc))


def collect_source_urls(
    *,
    source_urls: list[str] | None = None,
    primary_rules_url: str | None = None,
    rules_url: str | None = None,
    additional_urls: list[str] | None = None,
) -> list[str]:
    """Merge orchestrator / API URL fields into a deduplicated http(s) list."""
    ordered: list[str] = []

    def add(candidate: str | None) -> None:
        if not candidate:
            return
        stripped = str(candidate).strip()
        if stripped and stripped not in ordered:
            ordered.append(stripped)

    for url in source_urls or []:
        add(url)

    add(primary_rules_url)
    add(rules_url)

    for url in additional_urls or []:
        add(url)

    normalized: list[str] = []
    for url in ordered:
        page = _canonicalize_url(url)
        if page and page not in normalized:
            normalized.append(page)

    return normalized
