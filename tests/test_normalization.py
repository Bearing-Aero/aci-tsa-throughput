import socket
from datetime import date

import pytest

from tsa_throughput.exceptions import NormalizationError
from tsa_throughput.models import RawReportLink, ThroughputReport
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


@pytest.mark.parametrize(
    ("title", "filename", "expected_start", "expected_end", "expected_confidence"),
    [
        (
            "TSA Throughput Data to August 30, 2025 to August 9, 2025",
            "tsa-throughput-data-to-august-3-2025-to-august-9-2025.pdf",
            date(2025, 8, 3),
            date(2025, 8, 9),
            "title_invalid_url_used",
        ),
        (
            "TSA Throughput Data December 27, 2020 to January 2, 2020",
            "tsa-throughput-december-27-2020-to-january-2-2021.pdf",
            date(2020, 12, 27),
            date(2021, 1, 2),
            "title_invalid_url_used",
        ),
    ],
)
def test_invalid_title_ranges_use_valid_filename_dates(
    title: str,
    filename: str,
    expected_start: date,
    expected_end: date,
    expected_confidence: str,
) -> None:
    report = normalize_report_link(_raw(title=title, url=_tsa_url(filename)))

    _assert_report_dates(report, expected_start, expected_end)
    assert report.date_confidence == expected_confidence


@pytest.mark.parametrize(
    ("title", "filename", "expected_start", "expected_end"),
    [
        (
            "TSA Throughput Data to October 27, 2024 to November 2, 2024",
            "tsa-total-throughput-data-october-27-2924-to-november-2-2024.pdf",
            date(2024, 10, 27),
            date(2024, 11, 2),
        ),
        (
            "TSA Throughput Data September 19, 2021 to September 25, 2021",
            "tsa-throughput-september-19-2921-to-september-25-2021.pdf",
            date(2021, 9, 19),
            date(2021, 9, 25),
        ),
        (
            "TSA Throughput Data November 3, 2019 to November 9, 2019",
            "tsa_throughput_november_3_2019_to_november_9_2919.pdf",
            date(2019, 11, 3),
            date(2019, 11, 9),
        ),
    ],
)
def test_valid_title_dates_use_title_when_filename_year_is_invalid(
    title: str,
    filename: str,
    expected_start: date,
    expected_end: date,
) -> None:
    report = normalize_report_link(_raw(title=title, url=_tsa_url(filename)))

    _assert_report_dates(report, expected_start, expected_end)
    assert report.date_confidence == "url_invalid_title_used"


@pytest.mark.parametrize(
    ("title", "filename", "expected_start", "expected_end"),
    [
        (
            "TSA Throughput Data to February 23, 2025 to March 3, 2025",
            "tsa-total-throughput-data-february-23-2025-to-march-1-2025.pdf",
            date(2025, 2, 23),
            date(2025, 3, 1),
        ),
        (
            "TSA Throughput Data to February 9, 2025 to February 18, 2025",
            "tsa-total-throughput-data-february-9-2025-to-february-15-2025.pdf",
            date(2025, 2, 9),
            date(2025, 2, 15),
        ),
        (
            "TSA Throughput Data to September 22, 2024 to September 29, 2024",
            "tsa-total-throughput-data-september-22-2024-to-september-28-2024_0.pdf",
            date(2024, 9, 22),
            date(2024, 9, 28),
        ),
        (
            "TSA Throughput Data to July 6, 2023 to July 12, 2023",
            "tsa-total-throughput-data-august-6-2023-to-august-12-2023.pdf",
            date(2023, 8, 6),
            date(2023, 8, 12),
        ),
        (
            "TSA Throughput Data July 3, 2021 to July 9, 2021",
            "tsa-total-throughput-data-july-3-2022-to-july-9-2022_1.pdf",
            date(2022, 7, 3),
            date(2022, 7, 9),
        ),
    ],
)
def test_known_title_filename_conflicts_use_filename_dates(
    title: str,
    filename: str,
    expected_start: date,
    expected_end: date,
) -> None:
    report = normalize_report_link(_raw(title=title, url=_tsa_url(filename)))

    _assert_report_dates(report, expected_start, expected_end)
    assert report.title == title
    assert report.source_filename == filename
    assert report.date_confidence == "title_url_conflict"


@pytest.mark.parametrize(
    ("title", "filename", "expected_start", "expected_end"),
    [
        (
            "TSA Throughput February 5-11, 2017",
            "tsa_throughput_february_5-11_2017_0.pdf",
            date(2017, 2, 5),
            date(2017, 2, 11),
        ),
        (
            "TSA Throughput February 12-18, 2017",
            "tsa_throughput_february_12-18_2017.pdf",
            date(2017, 2, 12),
            date(2017, 2, 18),
        ),
        (
            "TSA Throughput February 19-25, 2017",
            "tsa_throughput_february_19-25_2017.pdf",
            date(2017, 2, 19),
            date(2017, 2, 25),
        ),
        (
            "TSA Throughput March 5-11, 2017",
            "tsa_throughput_march_5-11_2017.pdf",
            date(2017, 3, 5),
            date(2017, 3, 11),
        ),
        (
            "TSA Throughput March 12-18, 2017",
            "tsa_throughput_march_12-18_2017.pdf",
            date(2017, 3, 12),
            date(2017, 3, 18),
        ),
        (
            "TSA Throughput March 19-25, 2017",
            "tsa_throughput_march_19-25_2017.pdf",
            date(2017, 3, 19),
            date(2017, 3, 25),
        ),
    ],
)
def test_compact_legacy_same_month_ranges_normalize_dates(
    title: str,
    filename: str,
    expected_start: date,
    expected_end: date,
) -> None:
    report = normalize_report_link(_raw(title=title, url=_tsa_url(filename)))

    _assert_report_dates(report, expected_start, expected_end)
    assert report.date_confidence != "missing"


@pytest.mark.parametrize(
    ("title", "filename", "expected_start", "expected_end"),
    [
        (
            "TSA Throughput February 26-March 4, 2017",
            "tsa_throughput_february_26-march_4_2017.pdf",
            date(2017, 2, 26),
            date(2017, 3, 4),
        ),
        (
            "TSA Throughput March 26-April 1, 2017",
            "tsa_throughput_march_26-april_1_2017.pdf",
            date(2017, 3, 26),
            date(2017, 4, 1),
        ),
    ],
)
def test_compact_legacy_cross_month_ranges_normalize_dates(
    title: str,
    filename: str,
    expected_start: date,
    expected_end: date,
) -> None:
    report = normalize_report_link(_raw(title=title, url=_tsa_url(filename)))

    _assert_report_dates(report, expected_start, expected_end)
    assert report.date_confidence != "missing"


def test_xlsx_pdf_source_filename_normalizes_to_canonical_pdf_filename() -> None:
    title = "TSA Throughput Data January 15, 2017 to February 4, 2017"
    filename = "tsa-throughput-data-january-15-2017-to-february-4-2017.xlsx.pdf"
    report = normalize_report_link(_raw(title=title, url=_tsa_url(filename)))

    _assert_report_dates(report, date(2017, 1, 15), date(2017, 2, 4))
    assert report.title == title
    assert report.source_filename == filename
    assert report.canonical_filename == "tsa-throughput-week-ending-2017-02-04.pdf"
    assert report.date_confidence != "title_url_match"
    assert report.date_confidence != "missing"


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


def _tsa_url(filename: str) -> str:
    return f"https://www.tsa.gov/sites/default/files/foia-readingroom/{filename}"


def _assert_report_dates(
    report: ThroughputReport,
    expected_start: date,
    expected_end: date,
) -> None:
    assert report.week_start == expected_start
    assert report.week_end == expected_end
    assert report.canonical_id == f"tsa-throughput-week-ending-{expected_end.isoformat()}"
    assert report.canonical_filename == f"tsa-throughput-week-ending-{expected_end.isoformat()}.pdf"


def _filename_from_url(url: str) -> str | None:
    return url.rsplit("/", 1)[-1] or None
