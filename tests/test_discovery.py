import socket
from collections.abc import Callable
from pathlib import Path

import pytest

from tsa_throughput.discovery import TSA_READING_ROOM_URL, discover_report_links
from tsa_throughput.exceptions import DiscoveryError, PaginationError

FIXTURES_DIR = Path("tests/fixtures")
PAGE_0_URL = TSA_READING_ROOM_URL
PAGE_1_URL = (
    "https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=1"
)
FIRST_REPORT_URL = (
    "https://www.tsa.gov/sites/default/files/foia-readingroom/"
    "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
)
OLDER_REPORT_URL = (
    "https://www.tsa.gov/sites/default/files/foia-readingroom/"
    "tsa_throughput_april_30_2017_to_may_6_2017.pdf?download=1"
)


def test_discovery_extracts_throughput_pdf_links_from_saved_listing_fixture() -> None:
    links = discover_report_links(fetch_html=_fixture_fetcher(), max_pages=1)

    assert [link.url for link in links] == [FIRST_REPORT_URL, OLDER_REPORT_URL]
    assert links[0].title == "TSA Throughput Data to May 31, 2026 to June 6, 2026"
    assert links[1].title == "Older TSA throughput report"


def test_extracted_links_include_title_absolute_url_source_filename_and_listing_url() -> None:
    link = discover_report_links(fetch_html=_fixture_fetcher(), max_pages=1)[0]

    assert link.title == "TSA Throughput Data to May 31, 2026 to June 6, 2026"
    assert link.url == FIRST_REPORT_URL
    assert link.source_filename == "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
    assert link.listing_url == PAGE_0_URL
    assert link.source_page_url == PAGE_0_URL


def test_relative_pdf_urls_are_normalized_to_absolute_tsa_urls() -> None:
    links = discover_report_links(fetch_html=_fixture_fetcher(), max_pages=1)

    assert FIRST_REPORT_URL in {link.url for link in links}


def test_non_pdf_links_are_ignored() -> None:
    links = discover_report_links(fetch_html=_fixture_fetcher(), max_pages=1)

    assert all("/news/press/releases" not in link.url for link in links)


def test_non_throughput_pdfs_are_ignored() -> None:
    links = discover_report_links(fetch_html=_fixture_fetcher(), max_pages=1)

    assert all("tsa-budget-request-2026.pdf" not in link.url for link in links)


def test_duplicate_pdf_links_are_deduplicated() -> None:
    links = discover_report_links(fetch_html=_fixture_fetcher(), max_pages=1)

    assert [link.url for link in links].count(FIRST_REPORT_URL) == 1


def test_max_pages_one_only_fetches_one_page() -> None:
    calls: list[str] = []

    links = discover_report_links(fetch_html=_fixture_fetcher(calls=calls), max_pages=1)

    assert calls == [PAGE_0_URL]
    assert all("june-7-2026-to-june-13-2026" not in link.url for link in links)


def test_pagination_follows_next_link_when_present() -> None:
    calls: list[str] = []

    links = discover_report_links(fetch_html=_fixture_fetcher(calls=calls))

    assert calls == [PAGE_0_URL, PAGE_1_URL]
    assert any("june-7-2026-to-june-13-2026" in link.url for link in links)


def test_pagination_stops_when_no_next_link_exists() -> None:
    calls: list[str] = []

    links = discover_report_links(start_url=PAGE_1_URL, fetch_html=_fixture_fetcher(calls=calls))

    assert calls == [PAGE_1_URL]
    assert len(links) == 1


def test_pagination_loop_detection_raises_pagination_error() -> None:
    html = """
    <html>
      <body>
        <a href="/sites/default/files/foia-readingroom/tsa-throughput-loop.pdf">
          TSA throughput loop report
        </a>
        <a rel="next" href="?title=&amp;field_foia_tax_category_target_id=1132&amp;page=0">
          Next
        </a>
      </body>
    </html>
    """

    with pytest.raises(PaginationError):
        discover_report_links(fetch_html=lambda url: html)


def test_malformed_listing_pages_raise_discovery_error() -> None:
    with pytest.raises(DiscoveryError):
        discover_report_links(fetch_html=lambda url: "<html><body><h1>Broken</h1></body></html>")


def test_discovery_tests_do_not_make_live_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("discovery tests must use injected fixture HTML")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)

    links = discover_report_links(fetch_html=_fixture_fetcher(), max_pages=1)

    assert links


def _fixture_fetcher(calls: list[str] | None = None) -> Callable[[str], str]:
    pages = {
        PAGE_0_URL: (FIXTURES_DIR / "tsa_reading_room_page_0.html").read_text(encoding="utf-8"),
        PAGE_1_URL: (FIXTURES_DIR / "tsa_reading_room_page_1.html").read_text(encoding="utf-8"),
    }

    def fetch_html(url: str) -> str:
        if calls is not None:
            calls.append(url)
        return pages[url]

    return fetch_html
