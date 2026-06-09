"""Plain data models used across tsa-throughput."""

from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path


@dataclass(slots=True)
class RawReportLink:
    """Raw PDF link extracted from a TSA source page."""

    title: str
    url: str
    source_page_url: str | None = None
    source_page: int | None = None


@dataclass(slots=True)
class ThroughputReport:
    """Normalized metadata for a TSA throughput report."""

    source_url: str
    week_start: date | None = None
    week_end: date | None = None
    report_id: str | None = None
    title: str | None = None
    original_filename: str | None = None
    canonical_filename: str | None = None
    date_confidence: str = "unknown"
    alternate_urls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DownloadResult:
    """Result metadata for an attempted report download."""

    report: ThroughputReport
    status: str
    path: Path | None = None
    sha256: str | None = None
    size_bytes: int | None = None


@dataclass(slots=True)
class ThroughputRecord:
    """Canonical parsed TSA throughput record."""

    throughput_date: date
    airport_code: str
    throughput_count: int
    source_file: Path
    parser_name: str
    parser_version: str
    hour: time | None = None
    airport_name: str | None = None
    city: str | None = None
    state: str | None = None
    checkpoint_name: str | None = None
    metric_name: str | None = None
    metric_source_column: str | None = None
    week_start: date | None = None
    week_end: date | None = None
    source_url: str | None = None
    source_page: int | None = None
    source_table: int | None = None
    parse_confidence: str | None = None


@dataclass(slots=True)
class ParseResult:
    """Result metadata and records from parsing a throughput report."""

    source_file: Path
    parser_name: str
    parser_version: str
    records: list[ThroughputRecord] = field(default_factory=list)
    record_count: int = 0
    week_start: date | None = None
    week_end: date | None = None
    errors: list[str] = field(default_factory=list)

