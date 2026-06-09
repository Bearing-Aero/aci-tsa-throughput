"""Batch parsing orchestration helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from tsa_throughput.exceptions import ParseError, TSAThroughputError
from tsa_throughput.manifest import load_runtime_manifest
from tsa_throughput.models import (
    ParseResult,
    RuntimeManifest,
    RuntimeManifestEntry,
    ThroughputRecord,
    ThroughputReport,
)
from tsa_throughput.parsing.registry import get_parser

DEFAULT_PARSE_ALL_PATTERN = "*.pdf"
_WEEK_ENDING_PATTERN = re.compile(
    r"^tsa-throughput-week-ending-(?P<week_end>\d{4}-\d{2}-\d{2})$"
)


@dataclass(frozen=True, slots=True)
class BatchParseFailure:
    """One failed file from a batch parse run."""

    pdf_path: Path
    error: TSAThroughputError


@dataclass(slots=True)
class BatchParseResult:
    """Combined result metadata for a batch parse run."""

    pdf_paths: list[Path]
    parse_results: list[ParseResult] = field(default_factory=list)
    failures: list[BatchParseFailure] = field(default_factory=list)

    @property
    def pdf_count(self) -> int:
        """Return the number of matching PDF files found."""
        return len(self.pdf_paths)

    @property
    def parsed_count(self) -> int:
        """Return the number of PDF files parsed successfully."""
        return len(self.parse_results)

    @property
    def failed_count(self) -> int:
        """Return the number of PDF files that failed to parse."""
        return len(self.failures)

    @property
    def records(self) -> list[ThroughputRecord]:
        """Return all parsed records in input-file order."""
        return [
            record
            for parse_result in self.parse_results
            for record in parse_result.records
        ]

    @property
    def record_count(self) -> int:
        """Return the total number of parsed records."""
        return sum(parse_result.record_count for parse_result in self.parse_results)


def parse_reports_in_directory(
    input_dir: Path,
    *,
    pattern: str = DEFAULT_PARSE_ALL_PATTERN,
    max_pages: int | None = None,
    parser_name: str | None = None,
    continue_on_error: bool = False,
) -> BatchParseResult:
    """Parse matching PDF files in a local directory."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise ParseError(f"input directory does not exist or is not a directory: {input_dir}")

    pdf_paths = _find_pdf_paths(input_dir, pattern)
    if not pdf_paths:
        raise ParseError(f"no PDF files found in {input_dir} matching pattern {pattern!r}")

    manifest = load_runtime_manifest(input_dir / "manifest.json")
    reports_by_filename = _reports_by_filename(manifest)
    batch_result = BatchParseResult(pdf_paths=pdf_paths)

    for pdf_path in pdf_paths:
        report = reports_by_filename.get(pdf_path.name) or _minimal_report_from_path(pdf_path)

        try:
            parser = get_parser(report, pdf_path, parser_name=parser_name)
            parse_result = parser.parse(pdf_path, max_pages=max_pages, report=report)
        except TSAThroughputError as exc:
            batch_result.failures.append(BatchParseFailure(pdf_path=pdf_path, error=exc))
            if not continue_on_error:
                break
            continue

        batch_result.parse_results.append(parse_result)

    return batch_result


def _find_pdf_paths(input_dir: Path, pattern: str) -> list[Path]:
    return sorted(
        (path for path in input_dir.glob(pattern) if path.is_file()),
        key=lambda path: (path.name, str(path)),
    )


def _reports_by_filename(manifest: RuntimeManifest) -> dict[str, ThroughputReport]:
    reports: dict[str, ThroughputReport] = {}

    for entry in manifest.reports:
        report = _report_from_manifest_entry(entry)
        for filename in _entry_filenames(entry):
            reports[filename] = report

    return reports


def _entry_filenames(entry: RuntimeManifestEntry) -> set[str]:
    filenames = {
        Path(entry.local_path).name,
        entry.source_filename,
        entry.canonical_filename,
    }
    return {filename for filename in filenames if filename}


def _report_from_manifest_entry(entry: RuntimeManifestEntry) -> ThroughputReport:
    return ThroughputReport(
        source_url=entry.source_url,
        week_start=entry.week_start,
        week_end=entry.week_end,
        canonical_id=entry.canonical_id,
        source_filename=entry.source_filename,
        canonical_filename=entry.canonical_filename,
        date_confidence=entry.date_confidence,
    )


def _minimal_report_from_path(pdf_path: Path) -> ThroughputReport:
    week_start = None
    week_end = None
    date_confidence = "missing"

    match = _WEEK_ENDING_PATTERN.match(pdf_path.stem)
    if match is not None:
        week_end = _parse_week_end_from_filename(match.group("week_end"), pdf_path)
        week_start = week_end - timedelta(days=6)
        date_confidence = "filename_only"

    return ThroughputReport(
        source_url="",
        week_start=week_start,
        week_end=week_end,
        canonical_id=pdf_path.stem,
        source_filename=pdf_path.name,
        canonical_filename=pdf_path.name,
        date_confidence=date_confidence,
    )


def _parse_week_end_from_filename(value: str, pdf_path: Path) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ParseError(f"could not infer week_end from filename: {pdf_path.name}") from exc
