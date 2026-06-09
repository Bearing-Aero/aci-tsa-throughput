"""Report discovery helpers for TSA FOIA listing pages."""

from __future__ import annotations

import posixpath
import re
from collections.abc import Callable, Iterable
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag

from tsa_throughput.exceptions import DiscoveryError, PaginationError, TSAThroughputHTTPError
from tsa_throughput.models import RawReportLink

TSA_READING_ROOM_URL = (
    "https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=0"
)

_WHITESPACE_RE = re.compile(r"\s+")


def discover_report_links(
    start_url: str = TSA_READING_ROOM_URL,
    max_pages: int | None = None,
    fetch_html: Callable[[str], str] | None = None,
) -> list[RawReportLink]:
    """Discover raw TSA throughput PDF links from FOIA Reading Room listing pages."""
    if max_pages is not None and max_pages < 1:
        raise PaginationError("max_pages must be at least 1")

    fetch = fetch_html or _default_fetch_html
    current_url: str | None = start_url
    visited_urls: set[str] = set()
    discovered: list[RawReportLink] = []
    seen_report_urls: set[str] = set()
    pages_fetched = 0

    while current_url is not None:
        page_key = _url_key(current_url)
        if page_key in visited_urls:
            raise PaginationError(f"pagination loop detected at {current_url}")
        if max_pages is not None and pages_fetched >= max_pages:
            break

        visited_urls.add(page_key)
        html = _fetch_listing_html(fetch, current_url)
        soup = _parse_listing_html(html, current_url)

        for link in _extract_report_links(soup, current_url, pages_fetched):
            report_key = _url_key(link.url)
            if report_key in seen_report_urls:
                continue
            seen_report_urls.add(report_key)
            discovered.append(link)

        pages_fetched += 1
        next_url = _find_next_url(soup, current_url)
        if next_url is not None and _url_key(next_url) in visited_urls:
            raise PaginationError(f"pagination loop detected at {next_url}")
        current_url = next_url

    return discovered


def _default_fetch_html(url: str) -> str:
    try:
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise TSAThroughputHTTPError(f"could not fetch TSA listing page: {url}") from exc
    return response.text


def _fetch_listing_html(fetch_html: Callable[[str], str], url: str) -> str:
    try:
        html = fetch_html(url)
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(f"could not fetch TSA listing page: {url}") from exc

    if not isinstance(html, str) or not html.strip():
        raise DiscoveryError(f"empty TSA listing page: {url}")

    return html


def _parse_listing_html(html: str, listing_url: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    if not soup.find_all("a", href=True):
        raise DiscoveryError(f"malformed TSA listing page has no links: {listing_url}")
    return soup


def _extract_report_links(
    soup: BeautifulSoup,
    listing_url: str,
    source_page: int,
) -> Iterable[RawReportLink]:
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue

        href = str(anchor["href"]).strip()
        if not _is_pdf_href(href):
            continue

        absolute_url = urljoin(listing_url, href)
        source_filename = _source_filename(absolute_url)
        title = _link_title(anchor, source_filename)

        if not _looks_like_throughput_report(title, href, source_filename):
            continue

        yield RawReportLink(
            title=title,
            url=absolute_url,
            source_page_url=listing_url,
            source_page=source_page,
            source_filename=source_filename,
            listing_url=listing_url,
        )


def _find_next_url(soup: BeautifulSoup, current_url: str) -> str | None:
    for anchor in soup.find_all("a", href=True):
        if isinstance(anchor, Tag) and _has_next_rel(anchor):
            return urljoin(current_url, str(anchor["href"]).strip())

    for anchor in soup.find_all("a", href=True):
        if isinstance(anchor, Tag) and _is_next_link(anchor):
            return urljoin(current_url, str(anchor["href"]).strip())

    return None


def _is_pdf_href(href: str) -> bool:
    return urlsplit(href).path.lower().endswith(".pdf")


def _source_filename(url: str) -> str:
    path = urlsplit(url).path
    return unquote(posixpath.basename(path))


def _link_title(anchor: Tag, source_filename: str) -> str:
    text = _normalize_text(anchor.get_text(" ", strip=True))
    if text:
        return text

    for attribute_name in ("title", "aria-label"):
        attribute_value = anchor.get(attribute_name)
        if isinstance(attribute_value, str):
            text = _normalize_text(attribute_value)
            if text:
                return text

    return source_filename


def _looks_like_throughput_report(title: str, href: str, source_filename: str) -> bool:
    haystack = _normalize_for_matching(" ".join([title, href, source_filename]))
    return "throughput" in haystack and "tsa" in haystack


def _has_next_rel(anchor: Tag) -> bool:
    rel = anchor.get("rel")
    if isinstance(rel, str):
        return "next" in _normalize_for_matching(rel).split()
    if isinstance(rel, list):
        return any(isinstance(item, str) and item.lower() == "next" for item in rel)
    return False


def _is_next_link(anchor: Tag) -> bool:
    labels: list[str] = [anchor.get_text(" ", strip=True)]
    for attribute_name in ("aria-label", "title"):
        attribute_value = anchor.get(attribute_name)
        if isinstance(attribute_value, str):
            labels.append(attribute_value)

    return any(_is_next_label(label) for label in labels)


def _is_next_label(label: str) -> bool:
    normalized = _normalize_for_matching(label).strip()
    if normalized in {"next", "next page", "go to next page", ">", ">>"}:
        return True

    words = normalized.split()
    return "next" in words and "previous" not in words


def _normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


def _normalize_for_matching(value: str) -> str:
    return _normalize_text(value.replace("-", " ").replace("_", " ")).lower()


def _url_key(url: str) -> str:
    return urldefrag(urljoin(TSA_READING_ROOM_URL, url)).url
