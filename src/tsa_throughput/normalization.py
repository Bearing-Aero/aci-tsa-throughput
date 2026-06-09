"""Source metadata normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from tsa_throughput.exceptions import NormalizationError
from tsa_throughput.models import RawReportLink, ThroughputReport

DATE_CONFIDENCE_TITLE_URL_MATCH = "title_url_match"
DATE_CONFIDENCE_TITLE_ONLY = "title_only"
DATE_CONFIDENCE_URL_ONLY = "url_only"
DATE_CONFIDENCE_TITLE_URL_CONFLICT = "title_url_conflict"
DATE_CONFIDENCE_TITLE_INVALID_URL_USED = "title_invalid_url_used"
DATE_CONFIDENCE_URL_INVALID_TITLE_USED = "url_invalid_title_used"
DATE_CONFIDENCE_MISSING = "missing"

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTH_PATTERN = "|".join(_MONTHS)
_DATE_SEPARATOR = r"[\s_-]+"
_FULL_DATE_RANGE_PATTERN = re.compile(
    rf"(?<![a-z0-9])(?P<start_month>{_MONTH_PATTERN})"
    rf"{_DATE_SEPARATOR}"
    r"(?P<start_day>\d{1,2})"
    rf",?{_DATE_SEPARATOR}"
    r"(?P<start_year>\d{4})"
    rf"{_DATE_SEPARATOR}to{_DATE_SEPARATOR}"
    rf"(?P<end_month>{_MONTH_PATTERN})"
    rf"{_DATE_SEPARATOR}"
    r"(?P<end_day>\d{1,2})"
    rf",?{_DATE_SEPARATOR}"
    r"(?P<end_year>\d{4})(?=$|[^a-z0-9])",
    flags=re.IGNORECASE,
)
_COMPACT_CROSS_MONTH_DATE_RANGE_PATTERN = re.compile(
    rf"(?<![a-z0-9])(?P<start_month>{_MONTH_PATTERN})"
    rf"{_DATE_SEPARATOR}"
    r"(?P<start_day>\d{1,2})"
    r"\s*-\s*"
    rf"(?P<end_month>{_MONTH_PATTERN})"
    rf"{_DATE_SEPARATOR}"
    r"(?P<end_day>\d{1,2})"
    rf",?{_DATE_SEPARATOR}"
    r"(?P<year>\d{4})(?=$|[^a-z0-9])",
    flags=re.IGNORECASE,
)
_COMPACT_SAME_MONTH_DATE_RANGE_PATTERN = re.compile(
    rf"(?<![a-z0-9])(?P<start_month>{_MONTH_PATTERN})"
    rf"{_DATE_SEPARATOR}"
    r"(?P<start_day>\d{1,2})"
    r"\s*-\s*"
    r"(?P<end_day>\d{1,2})"
    rf",?{_DATE_SEPARATOR}"
    r"(?P<year>\d{4})(?=$|[^a-z0-9])",
    flags=re.IGNORECASE,
)
_DATE_RANGE_PATTERNS = (
    _FULL_DATE_RANGE_PATTERN,
    _COMPACT_CROSS_MONTH_DATE_RANGE_PATTERN,
    _COMPACT_SAME_MONTH_DATE_RANGE_PATTERN,
)
_UNSAFE_FILENAME_CHARS = re.compile(r"[^a-z0-9.-]+")
_DASH_RUN = re.compile(r"-+")
_NUMERIC_SUFFIX_PATTERN = re.compile(r"_[0-9]+$")
_MIN_VALID_RANGE_DAYS = 4
_MAX_VALID_RANGE_DAYS = 10
_FILENAME_DATE_OVERRIDES = {
    "tsa-total-throughput-data-february-23-2025-to-march-1-2025.pdf": (
        date(2025, 2, 23),
        date(2025, 3, 1),
    ),
    "tsa-total-throughput-data-february-9-2025-to-february-15-2025.pdf": (
        date(2025, 2, 9),
        date(2025, 2, 15),
    ),
    "tsa-total-throughput-data-september-22-2024-to-september-28-2024_0.pdf": (
        date(2024, 9, 22),
        date(2024, 9, 28),
    ),
    "tsa-total-throughput-data-august-6-2023-to-august-12-2023.pdf": (
        date(2023, 8, 6),
        date(2023, 8, 12),
    ),
    "tsa-total-throughput-data-july-3-2022-to-july-9-2022_1.pdf": (
        date(2022, 7, 3),
        date(2022, 7, 9),
    ),
    "tsa-throughput-data-january-15-2017-to-february-4-2017.xlsx.pdf": (
        date(2017, 1, 15),
        date(2017, 2, 4),
    ),
}


@dataclass(frozen=True, slots=True)
class _ExtractedDateRange:
    dates: tuple[date, date] | None = None
    invalid: bool = False


def normalize_report_link(raw: RawReportLink) -> ThroughputReport:
    """Normalize one raw FOIA report link into report metadata."""
    source_url = _required_url(raw.url)
    source_filename = _source_filename(raw, source_url)
    title = raw.title or ""

    title_dates = _extract_date_range(title)
    url_dates = _extract_date_range(_url_date_text(source_url, source_filename))
    filename_override = _filename_date_override(source_filename)
    week_start, week_end, date_confidence = _select_dates(
        title_dates,
        url_dates,
        filename_override,
    )
    canonical_id = _canonical_id(week_end, source_filename)
    canonical_filename = _canonical_filename(week_end, source_filename)

    return ThroughputReport(
        canonical_id=canonical_id,
        week_start=week_start,
        week_end=week_end,
        title=title,
        source_url=source_url,
        source_filename=source_filename,
        canonical_filename=canonical_filename,
        date_confidence=date_confidence,
        listing_url=raw.listing_url or raw.source_page_url,
    )


def normalize_report_links(raw_links: list[RawReportLink]) -> list[ThroughputReport]:
    """Normalize, de-duplicate, and sort raw FOIA report links."""
    reports_by_key: dict[tuple[str, str], ThroughputReport] = {}

    for raw in raw_links:
        report = normalize_report_link(raw)
        key = _dedupe_key(report)
        existing = reports_by_key.get(key)
        if existing is None:
            reports_by_key[key] = report
            continue

        existing.alternate_urls.append(report.source_url)

    return _sort_reports(list(reports_by_key.values()))


def _required_url(value: str | None) -> str:
    if value is None:
        raise NormalizationError("raw report link is missing source URL")
    source_url = value.strip()
    if not source_url:
        raise NormalizationError("raw report link is missing source URL")
    return source_url


def _source_filename(raw: RawReportLink, source_url: str) -> str:
    if raw.source_filename and raw.source_filename.strip():
        return raw.source_filename.strip()

    parsed = urlparse(source_url)
    name = unquote(PurePosixPath(parsed.path).name).strip()
    if not name:
        raise NormalizationError(f"could not derive source filename from URL: {source_url}")
    return name


def _url_date_text(source_url: str, source_filename: str) -> str:
    parsed = urlparse(source_url)
    path_text = unquote(parsed.path)
    return f"{source_filename} {path_text}"


def _filename_date_override(source_filename: str) -> tuple[date, date] | None:
    return _FILENAME_DATE_OVERRIDES.get(source_filename.lower())


def _extract_date_range(value: str) -> _ExtractedDateRange:
    searchable = _NUMERIC_SUFFIX_PATTERN.sub("", value)
    invalid = False

    for pattern in _DATE_RANGE_PATTERNS:
        for match in pattern.finditer(searchable):
            dates = _date_range_from_match(match)
            if dates is None or not _is_valid_week_range(*dates):
                invalid = True
                continue

            return _ExtractedDateRange(dates=dates)

    return _ExtractedDateRange(invalid=invalid)


def _date_range_from_match(match: re.Match[str]) -> tuple[date, date] | None:
    groups = match.groupdict()
    start_month = groups["start_month"].lower()
    end_month = (groups.get("end_month") or groups["start_month"]).lower()
    start_year = int(groups.get("start_year") or groups["year"])
    end_year = int(groups.get("end_year") or groups["year"])

    try:
        week_start = date(start_year, _MONTHS[start_month], int(groups["start_day"]))
        week_end = date(end_year, _MONTHS[end_month], int(groups["end_day"]))
    except ValueError:
        return None

    return week_start, week_end


def _is_valid_week_range(week_start: date, week_end: date) -> bool:
    range_days = (week_end - week_start).days
    return _MIN_VALID_RANGE_DAYS <= range_days <= _MAX_VALID_RANGE_DAYS


def _select_dates(
    title_dates: _ExtractedDateRange,
    url_dates: _ExtractedDateRange,
    filename_override: tuple[date, date] | None = None,
) -> tuple[date | None, date | None, str]:
    if filename_override is not None:
        if title_dates.dates is not None and title_dates.dates != filename_override:
            return filename_override[0], filename_override[1], DATE_CONFIDENCE_TITLE_URL_CONFLICT
        if title_dates.invalid:
            return (
                filename_override[0],
                filename_override[1],
                DATE_CONFIDENCE_TITLE_INVALID_URL_USED,
            )
        if url_dates.invalid:
            return filename_override[0], filename_override[1], DATE_CONFIDENCE_URL_ONLY

    if title_dates.dates is not None and url_dates.dates is not None:
        if title_dates.dates == url_dates.dates:
            return title_dates.dates[0], title_dates.dates[1], DATE_CONFIDENCE_TITLE_URL_MATCH
        return title_dates.dates[0], title_dates.dates[1], DATE_CONFIDENCE_TITLE_URL_CONFLICT
    if title_dates.dates is not None:
        confidence = (
            DATE_CONFIDENCE_URL_INVALID_TITLE_USED
            if url_dates.invalid
            else DATE_CONFIDENCE_TITLE_ONLY
        )
        return title_dates.dates[0], title_dates.dates[1], confidence
    if url_dates.dates is not None:
        confidence = (
            DATE_CONFIDENCE_TITLE_INVALID_URL_USED
            if title_dates.invalid
            else DATE_CONFIDENCE_URL_ONLY
        )
        return url_dates.dates[0], url_dates.dates[1], confidence
    return None, None, DATE_CONFIDENCE_MISSING


def _canonical_id(week_end: date | None, source_filename: str) -> str:
    if week_end is not None:
        return f"tsa-throughput-week-ending-{week_end.isoformat()}"
    return f"tsa-throughput-unknown-date-{_safe_stem(source_filename)}"


def _canonical_filename(week_end: date | None, source_filename: str) -> str:
    if week_end is not None:
        return f"tsa-throughput-week-ending-{week_end.isoformat()}.pdf"
    return f"tsa-throughput-unknown-date-{_safe_stem(source_filename)}.pdf"


def _safe_stem(source_filename: str) -> str:
    stem = PurePosixPath(source_filename).stem.lower()
    safe = _UNSAFE_FILENAME_CHARS.sub("-", stem)
    safe = _DASH_RUN.sub("-", safe).strip("-.")
    if not safe:
        raise NormalizationError(f"source filename cannot produce a safe stem: {source_filename!r}")
    return safe


def _dedupe_key(report: ThroughputReport) -> tuple[str, str]:
    if report.week_end is not None and report.canonical_id is not None:
        return "canonical_id", report.canonical_id
    return "source_url", report.source_url


def _sort_reports(reports: list[ThroughputReport]) -> list[ThroughputReport]:
    return sorted(
        reports,
        key=lambda report: (
            report.week_end is None,
            -(report.week_end.toordinal()) if report.week_end is not None else 0,
            report.canonical_id or report.source_url,
        ),
    )
