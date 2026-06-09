from __future__ import annotations

import json
import socket
from collections.abc import Callable
from pathlib import Path

import pytest

from tsa_throughput.discovery import TSA_READING_ROOM_URL
from tsa_throughput.models import SourceManifest
from tsa_throughput.source_manifest import (
    load_source_manifest,
    refresh_source_manifest,
    refresh_source_manifest_with_result,
)

PAGE_0_URL = TSA_READING_ROOM_URL
PAGE_1_URL = (
    "https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=1"
)
OLDER_CANONICAL_ID = "tsa-throughput-week-ending-2026-06-06"
NEWER_CANONICAL_ID = "tsa-throughput-week-ending-2026-06-13"
DUPLICATE_URL = (
    "https://www.tsa.gov/sites/default/files/foia-readingroom/"
    "tsa-throughput-data-duplicate-june-6-2026.pdf"
)
OLDER_PATH = (
    "/sites/default/files/foia-readingroom/"
    "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
)
DUPLICATE_PATH = (
    "/sites/default/files/foia-readingroom/"
    "tsa-throughput-data-duplicate-june-6-2026.pdf"
)
NEWER_CONFLICT_PATH = (
    "/sites/default/files/foia-readingroom/"
    "tsa-throughput-data-to-june-14-2026-to-june-20-2026.pdf"
)
NEXT_PATH = "/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=1"


def test_refresh_uses_fixture_discovery_without_live_network_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("live network calls are not allowed in refresh tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)

    manifest = refresh_source_manifest(fetch_html=_fixture_fetcher(calls))

    assert isinstance(manifest, SourceManifest)
    assert calls == [PAGE_0_URL, PAGE_1_URL]


def test_refresh_creates_source_manifest_from_discovered_raw_links() -> None:
    result = refresh_source_manifest_with_result(fetch_html=_fixture_fetcher())

    assert result.raw_report_count == 3
    assert result.manifest.source_name == "TSA FOIA Reading Room"
    assert result.manifest.reports


def test_refresh_normalizes_discovered_links_into_reports() -> None:
    manifest = refresh_source_manifest(fetch_html=_fixture_fetcher())
    report = next(
        item for item in manifest.reports if item.canonical_id == OLDER_CANONICAL_ID
    )

    assert report.week_start is not None
    assert report.week_start.isoformat() == "2026-05-31"
    assert report.week_end is not None
    assert report.week_end.isoformat() == "2026-06-06"
    assert report.canonical_filename == "tsa-throughput-week-ending-2026-06-06.pdf"


def test_refresh_writes_output_manifest_when_not_dry_run(tmp_path: Path) -> None:
    output_path = tmp_path / "source_manifest.json"

    manifest = refresh_source_manifest(
        output_path=output_path,
        fetch_html=_fixture_fetcher(),
    )

    assert output_path.is_file()
    assert load_source_manifest(output_path).reports == manifest.reports


def test_refresh_dry_run_does_not_write_output_manifest(tmp_path: Path) -> None:
    output_path = tmp_path / "source_manifest.json"

    manifest = refresh_source_manifest(
        output_path=output_path,
        fetch_html=_fixture_fetcher(),
        dry_run=True,
    )

    assert manifest.reports
    assert not output_path.exists()


def test_refresh_creates_output_parent_directories(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "manifests" / "source_manifest.json"

    refresh_source_manifest(output_path=output_path, fetch_html=_fixture_fetcher())

    assert output_path.is_file()


def test_refresh_sorts_manifest_reports_deterministically() -> None:
    manifest = refresh_source_manifest(fetch_html=_fixture_fetcher())

    assert [report.canonical_id for report in manifest.reports] == [
        NEWER_CANONICAL_ID,
        OLDER_CANONICAL_ID,
    ]


def test_refresh_preserves_date_confidence_values() -> None:
    manifest = refresh_source_manifest(fetch_html=_fixture_fetcher())
    report = next(
        item for item in manifest.reports if item.canonical_id == NEWER_CANONICAL_ID
    )

    assert report.date_confidence == "title_url_conflict"


def test_refresh_deduplicates_reports_through_normalization() -> None:
    manifest = refresh_source_manifest(fetch_html=_fixture_fetcher())
    report = next(
        item for item in manifest.reports if item.canonical_id == OLDER_CANONICAL_ID
    )

    assert len(manifest.reports) == 2
    assert report.alternate_urls == [DUPLICATE_URL]


def test_refresh_written_manifest_is_human_readable_json(tmp_path: Path) -> None:
    output_path = tmp_path / "source_manifest.json"

    refresh_source_manifest(output_path=output_path, fetch_html=_fixture_fetcher())

    text = output_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert "\n  " in text
    assert json.loads(text)["reports"]


def _fixture_fetcher(calls: list[str] | None = None) -> Callable[[str], str]:
    pages = {
        PAGE_0_URL: f"""
            <html>
              <body>
                <a href="{OLDER_PATH}">
                  TSA Throughput Data to May 31, 2026 to June 6, 2026
                </a>
                <a href="{DUPLICATE_PATH}">
                  TSA Throughput Data to May 31, 2026 to June 6, 2026
                </a>
                <a rel="next" href="{NEXT_PATH}">
                  Next
                </a>
              </body>
            </html>
        """,
        PAGE_1_URL: f"""
            <html>
              <body>
                <a href="{NEWER_CONFLICT_PATH}">
                  TSA Throughput Data to June 7, 2026 to June 13, 2026
                </a>
              </body>
            </html>
        """,
    }

    def fetch_html(url: str) -> str:
        if calls is not None:
            calls.append(url)
        return pages[url]

    return fetch_html
