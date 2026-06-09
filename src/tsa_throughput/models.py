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
    source_filename: str | None = None
    listing_url: str | None = None

    def __post_init__(self) -> None:
        """Keep old and new listing URL field names in sync."""
        if self.listing_url is None and self.source_page_url is not None:
            self.listing_url = self.source_page_url
        if self.source_page_url is None and self.listing_url is not None:
            self.source_page_url = self.listing_url


@dataclass(slots=True)
class ThroughputReport:
    """Normalized metadata for a TSA throughput report."""

    source_url: str
    week_start: date | None = None
    week_end: date | None = None
    canonical_id: str | None = None
    report_id: str | None = None
    title: str | None = None
    source_filename: str | None = None
    original_filename: str | None = None
    canonical_filename: str | None = None
    date_confidence: str = "unknown"
    listing_url: str | None = None
    alternate_urls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Keep legacy and canonical field names in sync."""
        if self.canonical_id is None and self.report_id is not None:
            self.canonical_id = self.report_id
        if self.report_id is None and self.canonical_id is not None:
            self.report_id = self.canonical_id
        if self.source_filename is None and self.original_filename is not None:
            self.source_filename = self.original_filename
        if self.original_filename is None and self.source_filename is not None:
            self.original_filename = self.source_filename


@dataclass(slots=True)
class DownloadResult:
    """Result metadata for an attempted report download."""

    report: ThroughputReport
    status: str
    path: Path | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    bytes: int | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        """Keep legacy and canonical byte-size field names in sync."""
        if self.size_bytes is None and self.bytes is not None:
            self.size_bytes = self.bytes
        if self.bytes is None and self.size_bytes is not None:
            self.bytes = self.size_bytes


@dataclass(frozen=True, slots=True)
class RuntimeManifestEntry:
    """One locally downloaded report entry in the runtime manifest."""

    canonical_id: str
    week_start: date | None
    week_end: date | None
    source_url: str
    source_filename: str
    canonical_filename: str
    local_path: str
    sha256: str
    bytes: int
    downloaded_at: str
    date_confidence: str


@dataclass(frozen=True, slots=True)
class RuntimeManifest:
    """Local runtime manifest of downloaded TSA throughput reports."""

    schema_version: int
    updated_at: str
    reports: list[RuntimeManifestEntry] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SourceManifest:
    """Installed catalog of known TSA source report metadata."""

    schema_version: int
    generated_at: str
    source_name: str
    source_listing_url: str
    reports: list[ThroughputReport] = field(default_factory=list)


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
