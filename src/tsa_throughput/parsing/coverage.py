"""Parser coverage scanning helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from tsa_throughput.exceptions import (
    ParseError,
    ParserNotFoundError,
    TSAThroughputError,
)
from tsa_throughput.manifest import load_runtime_manifest
from tsa_throughput.models import RuntimeManifest, RuntimeManifestEntry, ThroughputReport
from tsa_throughput.parsing.registry import get_parser

DEFAULT_COVERAGE_PATTERN = "*.pdf"

STATUS_PARSED = "parsed"
STATUS_NO_MATCHING_PARSER = "no_matching_parser"
STATUS_PARSE_ERROR = "parse_error"
STATUS_METADATA_MISSING = "metadata_missing"
STATUS_FILE_ERROR = "file_error"

_WEEK_ENDING_PATTERN = re.compile(
    r"^tsa-throughput-week-ending-(?P<week_end>\d{4}-\d{2}-\d{2})$"
)


@dataclass(frozen=True, slots=True)
class ParserCoverageResult:
    """Parser coverage outcome for one PDF file."""

    path: Path
    canonical_id: str | None
    week_end: date | None
    parser_name: str | None
    status: str
    record_count: int | None = None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ParserCoverageSummary:
    """Summary of a parser coverage scan."""

    scanned_count: int
    success_count: int
    failure_count: int
    skipped_count: int
    latest_success_week_end: date | None
    earliest_success_week_end: date | None
    first_failure_week_end: date | None
    first_failure_path: Path | None
    results: list[ParserCoverageResult] = field(default_factory=list)

    @property
    def first_failure(self) -> ParserCoverageResult | None:
        """Return the first parser failure, if present."""
        return next(
            (
                result
                for result in self.results
                if result.status
                in {
                    STATUS_NO_MATCHING_PARSER,
                    STATUS_PARSE_ERROR,
                    STATUS_FILE_ERROR,
                }
            ),
            None,
        )


def scan_parser_coverage(
    input_dir: Path,
    *,
    pattern: str = DEFAULT_COVERAGE_PATTERN,
    max_pages: int | None = None,
    stop_on_first_error: bool = False,
) -> ParserCoverageSummary:
    """Scan parser coverage for PDF files in a local directory."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise ParseError(f"input directory does not exist or is not a directory: {input_dir}")

    pdf_paths = _find_pdf_paths(input_dir, pattern)
    if not pdf_paths:
        raise ParseError(f"no PDF files found in {input_dir} matching pattern {pattern!r}")

    return scan_parser_coverage_for_paths(
        pdf_paths,
        manifest_path=input_dir / "manifest.json",
        max_pages=max_pages,
        stop_on_first_error=stop_on_first_error,
    )


def scan_parser_coverage_for_paths(
    paths: list[Path],
    *,
    manifest_path: Path | None = None,
    max_pages: int | None = None,
    stop_on_first_error: bool = False,
) -> ParserCoverageSummary:
    """Scan parser coverage for an explicit list of PDF paths."""
    manifest = (
        load_runtime_manifest(manifest_path)
        if manifest_path is not None
        else RuntimeManifest(schema_version=1, updated_at="", reports=[])
    )
    reports_by_filename = _reports_by_filename(manifest)
    candidates = [
        _CoverageCandidate(
            path=Path(path),
            report=_report_for_path(Path(path), reports_by_filename),
        )
        for path in paths
        if Path(path).is_file()
    ]
    candidates = sorted(candidates, key=_candidate_sort_key)

    results: list[ParserCoverageResult] = []
    success_seen = False

    for candidate in candidates:
        result = _scan_one_path(candidate.path, candidate.report, max_pages=max_pages)
        results.append(result)

        if result.status == STATUS_PARSED:
            success_seen = True
        elif (
            stop_on_first_error
            and success_seen
            and result.status
            in {
                STATUS_NO_MATCHING_PARSER,
                STATUS_PARSE_ERROR,
                STATUS_FILE_ERROR,
            }
        ):
            break

    return _summarize_results(results)


@dataclass(frozen=True, slots=True)
class _CoverageCandidate:
    path: Path
    report: ThroughputReport


def _find_pdf_paths(input_dir: Path, pattern: str) -> list[Path]:
    return [path for path in input_dir.glob(pattern) if path.is_file()]


def _scan_one_path(
    pdf_path: Path,
    report: ThroughputReport,
    *,
    max_pages: int | None,
) -> ParserCoverageResult:
    if report.week_end is None:
        return ParserCoverageResult(
            path=pdf_path,
            canonical_id=report.canonical_id,
            week_end=None,
            parser_name=None,
            status=STATUS_METADATA_MISSING,
            error_type=STATUS_METADATA_MISSING,
            error_message="week_end could not be inferred from manifest or filename",
        )

    try:
        parser = get_parser(report, pdf_path)
    except ParserNotFoundError as exc:
        return ParserCoverageResult(
            path=pdf_path,
            canonical_id=report.canonical_id,
            week_end=report.week_end,
            parser_name=None,
            status=STATUS_NO_MATCHING_PARSER,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    except OSError as exc:
        return ParserCoverageResult(
            path=pdf_path,
            canonical_id=report.canonical_id,
            week_end=report.week_end,
            parser_name=None,
            status=STATUS_FILE_ERROR,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

    try:
        parse_result = parser.parse(pdf_path, max_pages=max_pages, report=report)
    except OSError as exc:
        return ParserCoverageResult(
            path=pdf_path,
            canonical_id=report.canonical_id,
            week_end=report.week_end,
            parser_name=parser.parser_name,
            status=STATUS_FILE_ERROR,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    except TSAThroughputError as exc:
        return ParserCoverageResult(
            path=pdf_path,
            canonical_id=report.canonical_id,
            week_end=report.week_end,
            parser_name=parser.parser_name,
            status=STATUS_PARSE_ERROR,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

    return ParserCoverageResult(
        path=pdf_path,
        canonical_id=report.canonical_id,
        week_end=report.week_end,
        parser_name=parse_result.parser_name,
        status=STATUS_PARSED,
        record_count=parse_result.record_count,
    )


def _summarize_results(results: list[ParserCoverageResult]) -> ParserCoverageSummary:
    successes = [result for result in results if result.status == STATUS_PARSED]
    failures = [
        result
        for result in results
        if result.status
        in {
            STATUS_NO_MATCHING_PARSER,
            STATUS_PARSE_ERROR,
            STATUS_FILE_ERROR,
        }
    ]
    skipped = [result for result in results if result.status == STATUS_METADATA_MISSING]
    success_week_ends = [
        result.week_end for result in successes if result.week_end is not None
    ]
    first_failure = failures[0] if failures else None

    return ParserCoverageSummary(
        scanned_count=len(results),
        success_count=len(successes),
        failure_count=len(failures),
        skipped_count=len(skipped),
        latest_success_week_end=max(success_week_ends) if success_week_ends else None,
        earliest_success_week_end=min(success_week_ends) if success_week_ends else None,
        first_failure_week_end=first_failure.week_end if first_failure else None,
        first_failure_path=first_failure.path if first_failure else None,
        results=results,
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
        entry.local_path,
        entry.source_filename,
        entry.canonical_filename,
    }
    return {filename for filename in filenames if filename}


def _report_for_path(
    pdf_path: Path,
    reports_by_filename: dict[str, ThroughputReport],
) -> ThroughputReport:
    manifest_report = (
        reports_by_filename.get(str(pdf_path))
        or reports_by_filename.get(pdf_path.name)
        or reports_by_filename.get(pdf_path.as_posix())
    )
    filename_report = _minimal_report_from_path(pdf_path)

    if manifest_report is None:
        return filename_report

    if manifest_report.week_end is not None:
        return manifest_report

    return ThroughputReport(
        source_url=manifest_report.source_url,
        week_start=filename_report.week_start,
        week_end=filename_report.week_end,
        canonical_id=manifest_report.canonical_id or filename_report.canonical_id,
        source_filename=manifest_report.source_filename or filename_report.source_filename,
        canonical_filename=manifest_report.canonical_filename
        or filename_report.canonical_filename,
        date_confidence=(
            manifest_report.date_confidence
            if filename_report.week_end is None
            else filename_report.date_confidence
        ),
        listing_url=manifest_report.listing_url,
        alternate_urls=list(manifest_report.alternate_urls),
    )


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
        week_end = _parse_week_end_from_filename(match.group("week_end"))
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


def _parse_week_end_from_filename(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _candidate_sort_key(candidate: _CoverageCandidate) -> tuple[int, int, str]:
    week_end = candidate.report.week_end
    if week_end is None:
        return (1, 0, candidate.path.name)
    return (0, -week_end.toordinal(), candidate.path.name)
