"""Parser for historical PMIS PDFs with a merged first data row header."""

from __future__ import annotations

import re
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

import pdfplumber

from tsa_throughput.exceptions import ParseError
from tsa_throughput.models import ParseResult, ThroughputRecord, ThroughputReport
from tsa_throughput.parsing.base import ThroughputParser
from tsa_throughput.parsing.plugins import (
    historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber as pmis_parser,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    TABLE_SETTINGS,
    _clean_cell,
    _normalize_header_cell,
    _parse_count,
    _parse_date,
    _parse_hour,
)

PARSER_NAME = "historical_merged_header_pmis_pdfplumber"
PARSER_VERSION = "0.1.0"
LAYOUT_FAMILY = "hourly_checkpoint_pmis_total_customer_throughput_merged_header"
METRIC_NAME = pmis_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = pmis_parser.METRIC_SOURCE_COLUMN
PARSE_CONFIDENCE = "medium"

EXPECTED_COLUMN_COUNT = 9
_REPORT_FILTER_START_DATE_PATTERN = re.compile(
    r"Between\s+(?P<week_start>\d{1,2}/\d{1,2}/\d{4})\s+and",
    re.IGNORECASE,
)
_WEEK_ENDING_FILENAME_PATTERN = re.compile(
    r"tsa-throughput-week-ending-(?P<week_end>\d{4}-\d{2}-\d{2})\.pdf$"
)


class HistoricalMergedHeaderPmisPdfplumberParser(ThroughputParser):
    """Parse a PMIS layout where the first data row is embedded in the header."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY
    table_settings = TABLE_SETTINGS

    def can_parse(self, report: ThroughputReport, pdf_path: Path) -> bool:
        """Return whether the PDF contains the merged-header PMIS layout."""
        del report

        try:
            with pdfplumber.open(Path(pdf_path)) as pdf:
                pages_to_check = min(len(pdf.pages), 3)
                for page_index in range(pages_to_check):
                    tables = pdf.pages[page_index].extract_tables(
                        table_settings=self.table_settings
                    )
                    if any(
                        table and self._is_merged_header_row(_clean_row(table[0]))
                        for table in tables
                    ):
                        return True
        except Exception:
            return False

        return False

    def parse(
        self,
        source_file: Path,
        *,
        max_pages: int | None = None,
        report: ThroughputReport | None = None,
    ) -> ParseResult:
        """Parse a merged-header historical PMIS TSA throughput PDF."""
        source_file = Path(source_file)
        records: list[ThroughputRecord] = []

        try:
            with pdfplumber.open(source_file) as pdf:
                current_date = _initial_week_start(pdf, source_file, report)
                current_hour = time(0, 0)
                current_airport_code: str | None = None
                current_airport_name: str | None = None
                current_city: str | None = None
                current_state: str | None = None

                page_count = len(pdf.pages)
                pages_to_process = page_count if max_pages is None else min(
                    page_count, max_pages
                )

                for page_index in range(pages_to_process):
                    source_page = page_index + 1
                    tables = pdf.pages[page_index].extract_tables(
                        table_settings=self.table_settings
                    )
                    if not tables:
                        raise self._error(
                            source_file=source_file,
                            source_page=source_page,
                            reason="no merged-header PMIS table found",
                        )

                    for source_table, table in enumerate(tables, start=1):
                        rows = self._data_rows_from_table(
                            table,
                            source_file=source_file,
                            source_page=source_page,
                            source_table=source_table,
                        )
                        for row_index, row in enumerate(rows, start=1):
                            (
                                record,
                                current_date,
                                current_hour,
                                current_airport_code,
                                current_airport_name,
                                current_city,
                                current_state,
                            ) = self._parse_data_row(
                                row,
                                source_file=source_file,
                                source_page=source_page,
                                source_table=source_table,
                                row_index=row_index,
                                report=report,
                                current_date=current_date,
                                current_hour=current_hour,
                                current_airport_code=current_airport_code,
                                current_airport_name=current_airport_name,
                                current_city=current_city,
                                current_state=current_state,
                            )
                            if record is not None:
                                records.append(record)
        except ParseError:
            raise
        except Exception as exc:
            raise self._error(
                source_file=source_file,
                reason=f"failed to parse PDF: {exc}",
            ) from exc

        if not records:
            raise self._error(source_file=source_file, reason="no records produced")

        return ParseResult(
            source_file=source_file,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            records=records,
            record_count=len(records),
            week_start=report.week_start if report else None,
            week_end=report.week_end if report else None,
        )

    def _data_rows_from_table(
        self,
        table: list[list[Any]],
        *,
        source_file: Path,
        source_page: int,
        source_table: int,
    ) -> list[list[str | None]]:
        if not table:
            raise self._error(
                source_file=source_file,
                source_page=source_page,
                source_table=source_table,
                reason="empty table",
            )

        cleaned_rows = [_clean_row(row) for row in table]
        first_row = cleaned_rows[0]
        if self._is_merged_header_row(first_row):
            return [self._row_from_merged_header(first_row)] + cleaned_rows[1:]

        if self._is_clean_pmis_header_row(first_row):
            raise self._error(
                source_file=source_file,
                source_page=source_page,
                source_table=source_table,
                reason="clean PMIS header found instead of merged-header layout",
            )

        if len(first_row) == EXPECTED_COLUMN_COUNT and (
            first_row[2] or first_row[6] or first_row[8]
        ):
            return cleaned_rows

        raise self._error(
            source_file=source_file,
            source_page=source_page,
            source_table=source_table,
            reason="no merged-header PMIS data rows found",
        )

    def _is_merged_header_row(self, row: list[str | None]) -> bool:
        if len(row) != EXPECTED_COLUMN_COUNT:
            return False

        return (
            _normalize_header_cell(row[0]) == "date"
            and _normalize_header_cell(row[1]) == "day"
            and _normalized_startswith(row[2], "airport ")
            and row[3] is None
            and _normalized_startswith(row[4], "city ")
            and _normalized_startswith(row[5], "state ")
            and _normalized_startswith(row[6], "checkpoint ")
            and _normalize_header_cell(row[7]) == "metrics"
            and _normalized_startswith(row[8], "throughput (unadjusted) ")
        )

    def _is_clean_pmis_header_row(self, row: list[str | None]) -> bool:
        if len(row) != EXPECTED_COLUMN_COUNT:
            return False

        normalized = [_normalize_header_cell(cell) for cell in row]
        return (
            normalized[0] == "date"
            and normalized[1] == "hour of day"
            and normalized[2] == "airport"
            and normalized[4] == "city"
            and normalized[5] == "state"
            and normalized[6] == "checkpoint"
            and normalized[7] == "metrics"
            and normalized[8] == "pmis - total customer throughput (unadjusted)"
        )

    def _row_from_merged_header(self, row: list[str | None]) -> list[str | None]:
        airport_value = _strip_prefixed_value(row[2], "Airport")
        airport_parts = airport_value.split(maxsplit=1)
        if len(airport_parts) != 2:
            raise ParseError(
                f"{self.parser_name} failed to parse merged airport header: {row[2]!r}"
            )

        return [
            None,
            None,
            airport_parts[0],
            airport_parts[1],
            _strip_prefixed_value(row[4], "City"),
            _strip_prefixed_value(row[5], "State"),
            _strip_prefixed_value(row[6], "Checkpoint"),
            None,
            _strip_prefixed_value(row[8], "Throughput (Unadjusted)"),
        ]

    def _parse_data_row(
        self,
        row: list[str | None],
        *,
        source_file: Path,
        source_page: int,
        source_table: int,
        row_index: int,
        report: ThroughputReport | None,
        current_date: date,
        current_hour: time,
        current_airport_code: str | None,
        current_airport_name: str | None,
        current_city: str | None,
        current_state: str | None,
    ) -> tuple[
        ThroughputRecord | None,
        date,
        time,
        str | None,
        str | None,
        str | None,
        str | None,
    ]:
        if len(row) != EXPECTED_COLUMN_COUNT:
            if any(row):
                raise self._row_error(
                    source_file,
                    source_page,
                    source_table,
                    row_index,
                    f"expected {EXPECTED_COLUMN_COUNT} columns, found {len(row)}",
                )
            return (
                None,
                current_date,
                current_hour,
                current_airport_code,
                current_airport_name,
                current_city,
                current_state,
            )

        raw_date = row[0]
        raw_hour = row[1]
        raw_airport_code = row[2]
        raw_airport_name = row[3]
        raw_city = row[4]
        raw_state = row[5]
        raw_checkpoint = row[6]
        raw_count = row[8]

        if raw_date:
            try:
                current_date = _parse_date(raw_date)
            except ParseError as exc:
                raise self._row_error(
                    source_file,
                    source_page,
                    source_table,
                    row_index,
                    str(exc),
                ) from exc

        if raw_hour:
            try:
                parsed_hour = _parse_hour(raw_hour)
            except ParseError as exc:
                raise self._row_error(
                    source_file,
                    source_page,
                    source_table,
                    row_index,
                    str(exc),
                ) from exc
            if parsed_hour < current_hour:
                current_date += timedelta(days=1)
            current_hour = parsed_hour

        if raw_airport_code:
            current_airport_code = raw_airport_code.upper()
            current_airport_name = raw_airport_name
            current_city = raw_city
            current_state = raw_state.upper() if raw_state else None

        if not raw_checkpoint and raw_count is None:
            return (
                None,
                current_date,
                current_hour,
                current_airport_code,
                current_airport_name,
                current_city,
                current_state,
            )

        if current_airport_code is None:
            raise self._row_error(
                source_file,
                source_page,
                source_table,
                row_index,
                "missing airport context",
            )

        if not raw_checkpoint:
            raise self._row_error(
                source_file,
                source_page,
                source_table,
                row_index,
                "missing checkpoint",
            )

        if raw_count is None:
            raise self._row_error(
                source_file,
                source_page,
                source_table,
                row_index,
                "missing throughput count",
            )

        try:
            throughput_count = _parse_count(raw_count)
        except ParseError as exc:
            raise self._row_error(
                source_file,
                source_page,
                source_table,
                row_index,
                str(exc),
            ) from exc

        return (
            ThroughputRecord(
                throughput_date=current_date,
                hour=current_hour,
                airport_code=current_airport_code,
                airport_name=current_airport_name,
                city=current_city,
                state=current_state,
                checkpoint_name=raw_checkpoint,
                metric_name=METRIC_NAME,
                metric_source_column=METRIC_SOURCE_COLUMN,
                throughput_count=throughput_count,
                week_start=report.week_start if report else None,
                week_end=report.week_end if report else None,
                source_file=source_file,
                source_url=report.source_url if report else None,
                source_page=source_page,
                source_table=source_table,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                parse_confidence=PARSE_CONFIDENCE,
            ),
            current_date,
            current_hour,
            current_airport_code,
            current_airport_name,
            current_city,
            current_state,
        )

    def _row_error(
        self,
        source_file: Path,
        source_page: int,
        source_table: int,
        row_index: int,
        reason: str,
    ) -> ParseError:
        return self._error(
            source_file=source_file,
            source_page=source_page,
            source_table=source_table,
            reason=f"{reason} on row {row_index}",
        )

    def _error(
        self,
        *,
        source_file: Path,
        reason: str,
        source_page: int | None = None,
        source_table: int | None = None,
    ) -> ParseError:
        parts = [f"{self.parser_name} failed for {source_file}", f"reason: {reason}"]
        if source_page is not None:
            parts.append(f"page: {source_page}")
        if source_table is not None:
            parts.append(f"table: {source_table}")
        return ParseError("; ".join(parts))


def _initial_week_start(
    pdf: pdfplumber.PDF,
    source_file: Path,
    report: ThroughputReport | None,
) -> date:
    if report and report.week_start:
        return report.week_start

    first_page_text = pdf.pages[0].extract_text() if pdf.pages else None
    if first_page_text:
        match = _REPORT_FILTER_START_DATE_PATTERN.search(first_page_text)
        if match:
            return _parse_date(match.group("week_start"))

    filename_match = _WEEK_ENDING_FILENAME_PATTERN.match(source_file.name)
    if filename_match:
        return date.fromisoformat(filename_match.group("week_end")) - timedelta(days=6)

    raise ParseError(f"could not infer week start for {source_file}")


def _clean_row(row: list[Any]) -> list[str | None]:
    return [_clean_cell(cell) for cell in row]


def _normalized_startswith(value: str | None, prefix: str) -> bool:
    return _normalize_header_cell(value).startswith(prefix)


def _strip_prefixed_value(value: str | None, prefix: str) -> str:
    if value is None:
        raise ParseError(f"missing {prefix.lower()} value")

    normalized_prefix = prefix.casefold()
    if not value.casefold().startswith(normalized_prefix):
        raise ParseError(f"expected {prefix!r} prefix in {value!r}")

    stripped = value[len(prefix) :].strip()
    if not stripped:
        raise ParseError(f"missing value after {prefix!r} prefix")
    return stripped
