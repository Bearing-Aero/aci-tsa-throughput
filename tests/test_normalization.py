import socket
from datetime import date

import pytest

from tsa_throughput.exceptions import NormalizationError
from tsa_throughput.models import RawReportLink
from tsa_throughput.normalization import normalize_report_link, normalize_report_links

MODERN_TITLE = "TSA Throughput Data to May 31, 2026 to June 6, 2026"
MODERN_FILENAME = "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
MODERN_URL = f"https://www.tsa.gov/sites/default/files/foia-readingroom/{MODERN_FILENAME}"


def test_modern_title_and_filename_normalize_week_dates() -> None:
    report = normalize_report_link(_raw(title=MODERN_TITLE, url=MODERN_URL))

    assert report.week_start == date(2026, 5, 31)
    assert report.week_end == date(2026, 6, 6)
    assert report.title == MODERN_TITLE
    assert report.source_url == MODERN_URL
    assert report.source_filename == MODERN_FILENAME


def test_hyphenated_modern_filename_is_parsed() -> None:
    report = normalize_report_link(_raw(title="Weekly report", url=MODERN_URL))

    assert report.week_start == date(2026, 5, 31)
    assert report.week_end == date(2026, 6, 6)


def test_underscored_legacy_filename_is_parsed() -> None:
    filename = "tsa_throughput_april_30_2017_to_may_6_2017.pdf"
    report = normalize_report_link(
        _raw(title="Older TSA throughput report", url=f"https://www.tsa.gov/{filename}")
    )

    assert report.week_start == date(2017, 4, 30)
    assert report.week_end == date(2017, 5, 6)


def test_month_names_are_parsed_case_insensitively() -> None:
    title = "TSA Throughput Data to mAY 31, 2026 to JUNE 6, 2026"
    report = normalize_report_link(_raw(title=title, url="https://www.tsa.gov/report.pdf"))

    assert report.week_start == date(2026, 5, 31)
    assert report.week_end == date(2026, 6, 6)


def test_numeric_filename_suffix_is_ignored_for_date_extraction() -> None:
    filename = "tsa-throughput-data-to-may-31-2026-to-june-6-2026_0.pdf"
    report = normalize_report_link(
        _raw(title="Weekly report", url=f"https://www.tsa.gov/{filename}")
    )

    assert report.week_start == date(2026, 5, 31)
    assert report.week_end == date(2026, 6, 6)


def test_matching_title_and_url_dates_have_title_url_match_confidence() -> None:
    report = normalize_report_link(_raw(title=MODERN_TITLE, url=MODERN_URL))

    assert report.date_confidence == "title_url_match"


def test_title_only_dates_have_title_only_confidence() -> None:
    report = normalize_report_link(_raw(title=MODERN_TITLE, url="https://www.tsa.gov/report.pdf"))

    assert report.week_end == date(2026, 6, 6)
    assert report.date_confidence == "title_only"


def test_url_only_dates_have_url_only_confidence() -> None:
    report = normalize_report_link(_raw(title="Weekly report", url=MODERN_URL))

    assert report.week_end == date(2026, 6, 6)
    assert report.date_confidence == "url_only"


def test_conflicting_title_and_url_dates_preserve_title_dates_and_mark_conflict() -> None:
    title = "TSA Throughput Data to June 7, 2026 to June 13, 2026"
    report = normalize_report_link(_raw(title=title, url=MODERN_URL))

    assert report.week_start == date(2026, 6, 7)
    assert report.week_end == date(2026, 6, 13)
    assert report.date_confidence == "title_url_conflict"


def test_missing_dates_have_missing_confidence_and_safe_fallback_filename() -> None:
    report = normalize_report_link(
        _raw(title="Weekly report", url="https://www.tsa.gov/My Unsafe Report!.pdf")
    )

    assert report.week_start is None
    assert report.week_end is None
    assert report.date_confidence == "missing"
    assert report.canonical_filename == "tsa-throughput-unknown-date-my-unsafe-report.pdf"


def test_canonical_id_uses_week_end_date() -> None:
    report = normalize_report_link(_raw(title=MODERN_TITLE, url=MODERN_URL))

    assert report.canonical_id == "tsa-throughput-week-ending-2026-06-06"
    assert report.report_id == report.canonical_id


def test_canonical_filename_uses_week_end_date() -> None:
    report = normalize_report_link(_raw(title=MODERN_TITLE, url=MODERN_URL))

    assert report.canonical_filename == "tsa-throughput-week-ending-2026-06-06.pdf"


def test_normalize_report_links_deduplicates_matching_canonical_ids() -> None:
    duplicate_url = "https://www.tsa.gov/duplicate.pdf"
    reports = normalize_report_links(
        [
            _raw(title=MODERN_TITLE, url=MODERN_URL),
            _raw(title=MODERN_TITLE, url=duplicate_url),
        ]
    )

    assert len(reports) == 1
    assert reports[0].source_url == MODERN_URL


def test_duplicate_urls_are_preserved_in_alternate_urls() -> None:
    duplicate_url = "https://www.tsa.gov/duplicate.pdf"
    reports = normalize_report_links(
        [
            _raw(title=MODERN_TITLE, url=MODERN_URL),
            _raw(title=MODERN_TITLE, url=duplicate_url),
        ]
    )

    assert reports[0].alternate_urls == [duplicate_url]


def test_reports_sort_deterministically() -> None:
    older = _raw(title=MODERN_TITLE, url=MODERN_URL)
    newer = _raw(
        title="TSA Throughput Data to June 7, 2026 to June 13, 2026",
        url="https://www.tsa.gov/tsa-throughput-data-to-june-7-2026-to-june-13-2026.pdf",
    )
    missing = _raw(title="Weekly report", url="https://www.tsa.gov/report.pdf")

    reports = normalize_report_links([missing, older, newer])

    assert [report.week_end for report in reports] == [
        date(2026, 6, 13),
        date(2026, 6, 6),
        None,
    ]


def test_missing_source_url_raises_normalization_error() -> None:
    with pytest.raises(NormalizationError):
        normalize_report_link(_raw(title=MODERN_TITLE, url=""))


def test_missing_filename_is_derived_from_url_path() -> None:
    report = normalize_report_link(
        RawReportLink(
            title="Weekly report",
            url=MODERN_URL,
            source_filename=None,
        )
    )

    assert report.source_filename == MODERN_FILENAME
    assert report.original_filename == MODERN_FILENAME


def test_normalization_does_not_make_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("normalization must not make network calls")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)

    report = normalize_report_link(_raw(title=MODERN_TITLE, url=MODERN_URL))

    assert report.week_end == date(2026, 6, 6)


def _raw(title: str, url: str) -> RawReportLink:
    return RawReportLink(title=title, url=url, source_filename=_filename_from_url(url))


def _filename_from_url(url: str) -> str | None:
    return url.rsplit("/", 1)[-1] or None
