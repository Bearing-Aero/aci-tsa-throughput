"""Parser for the modern TSA hourly checkpoint throughput PDF layout."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pdfplumber

from tsa_throughput.exceptions import ParseError
from tsa_throughput.models import ParseResult, ThroughputRecord, ThroughputReport
from tsa_throughput.parsing.base import ThroughputParser

PARSER_NAME = "modern_total_pax_kcm_hourly_checkpoint_pdfplumber"
PARSER_VERSION = "0.1.0"
LAYOUT_FAMILY = "hourly_checkpoint_total_pax_kcm"
METRIC_NAME = "total_pax_plus_kcm_pax"
METRIC_SOURCE_COLUMN = "Total Pax + KCM PAX"
PARSE_CONFIDENCE = "high"

TABLE_SETTINGS: dict[str, Any] = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 3,
}

EXPECTED_COLUMN_COUNT = 8


class ModernTotalPaxKcmHourlyCheckpointPdfplumberParser(ThroughputParser):
    """Parse modern TSA PDFs with hourly airport/checkpoint total throughput tables."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY

    def can_parse(self, report: ThroughputReport, pdf_path: Path) -> bool:
        """Return whether the PDF contains a modern-layout throughput table."""
        del report

        try:
            with pdfplumber.open(Path(pdf_path)) as pdf:
                pages_to_check = min(len(pdf.pages), 5)
                for page_index in range(pages_to_check):
                    source_page = page_index + 1
                    tables = pdf.pages[page_index].extract_tables(table_settings=TABLE_SETTINGS)
                    if self._matching_tables(
                        tables,
                        source_file=Path(pdf_path),
                        source_page=source_page,
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
        """Parse a modern TSA throughput PDF."""
        source_file = Path(source_file)
        records: list[ThroughputRecord] = []

        try:
            with pdfplumber.open(source_file) as pdf:
                page_count = len(pdf.pages)
                pages_to_process = page_count if max_pages is None else min(page_count, max_pages)

                for page_index in range(pages_to_process):
                    source_page = page_index + 1
                    tables = pdf.pages[page_index].extract_tables(table_settings=TABLE_SETTINGS)
                    matching_tables = self._matching_tables(
                        tables,
                        source_file=source_file,
                        source_page=source_page,
                    )

                    if not matching_tables:
                        raise self._error(
                            source_file=source_file,
                            source_page=source_page,
                            reason="no matching modern throughput table found",
                        )

                    for table_index, table in enumerate(matching_tables, start=1):
                        records.extend(
                            self.parse_table(
                                table,
                                source_file=source_file,
                                source_page=source_page,
                                source_table=table_index,
                                report=report,
                            )
                        )
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

    def parse_table(
        self,
        table: list[list[Any]],
        *,
        source_file: Path,
        source_page: int,
        source_table: int,
        report: ThroughputReport | None = None,
    ) -> list[ThroughputRecord]:
        """Parse one extracted modern-layout table into throughput records."""
        if not table:
            raise self._error(
                source_file=source_file,
                source_page=source_page,
                source_table=source_table,
                reason="empty table",
            )

        cleaned_rows = [[_clean_cell(cell) for cell in row] for row in table]
        self._validate_header(
            cleaned_rows[0],
            source_file=source_file,
            source_page=source_page,
            source_table=source_table,
        )

        records: list[ThroughputRecord] = []
        current_date: date | None = None
        current_hour: time | None = None
        current_airport_code: str | None = None
        current_airport_name: str | None = None
        current_city: str | None = None
        current_state: str | None = None

        for row_index, row in enumerate(cleaned_rows[1:], start=2):
            if len(row) != EXPECTED_COLUMN_COUNT:
                if any(row):
                    raise self._row_error(
                        source_file,
                        source_page,
                        source_table,
                        row_index,
                        f"expected {EXPECTED_COLUMN_COUNT} columns, found {len(row)}",
                    )
                continue

            raw_date = row[0]
            raw_hour = row[1]
            raw_airport_code = row[2]
            raw_airport_name = row[3]
            raw_city = row[4]
            raw_state = row[5]
            raw_checkpoint = row[6]
            raw_count = row[7]

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
                    current_hour = _parse_hour(raw_hour)
                except ParseError as exc:
                    raise self._row_error(
                        source_file,
                        source_page,
                        source_table,
                        row_index,
                        str(exc),
                    ) from exc
            if raw_airport_code:
                current_airport_code = raw_airport_code.upper()
                current_airport_name = raw_airport_name
                current_city = raw_city
                current_state = raw_state.upper() if raw_state else None
            else:
                current_airport_name = (
                    raw_airport_name if raw_airport_name else current_airport_name
                )
                current_city = raw_city if raw_city else current_city
                current_state = raw_state.upper() if raw_state else current_state

            if not raw_checkpoint and raw_count is None:
                continue

            self._require_context(
                source_file=source_file,
                source_page=source_page,
                source_table=source_table,
                row_index=row_index,
                throughput_date=current_date,
                hour=current_hour,
                airport_code=current_airport_code,
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

            records.append(
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
                )
            )

        if not records:
            raise self._error(
                source_file=source_file,
                source_page=source_page,
                source_table=source_table,
                reason="no records produced",
            )

        return records

    def _matching_tables(
        self,
        tables: list[list[list[Any]]] | None,
        *,
        source_file: Path,
        source_page: int,
    ) -> list[list[list[Any]]]:
        if not tables:
            return []

        matching_tables: list[list[list[Any]]] = []
        for table_index, table in enumerate(tables, start=1):
            if not table:
                continue

            cleaned_header = [_clean_cell(cell) for cell in table[0]]
            try:
                self._validate_header(
                    cleaned_header,
                    source_file=source_file,
                    source_page=source_page,
                    source_table=table_index,
                )
            except ParseError:
                continue

            matching_tables.append(table)

        return matching_tables

    def _validate_header(
        self,
        header: list[str | None],
        *,
        source_file: Path,
        source_page: int,
        source_table: int,
    ) -> None:
        if len(header) != EXPECTED_COLUMN_COUNT:
            raise self._error(
                source_file=source_file,
                source_page=source_page,
                source_table=source_table,
                reason=f"expected {EXPECTED_COLUMN_COUNT} columns, found {len(header)}",
            )

        normalized = [_normalize_header_cell(cell) for cell in header]
        expected = {
            0: "date",
            1: "hour of day",
            2: "airport",
            4: "city",
            5: "state",
            6: "checkpoint",
            7: "total pax + kcm pax",
        }

        for index, expected_value in expected.items():
            if normalized[index] != expected_value:
                raise self._error(
                    source_file=source_file,
                    source_page=source_page,
                    source_table=source_table,
                    reason=(
                        f"unexpected header at column {index}: "
                        f"expected {expected_value!r}, found {header[index]!r}"
                    ),
                )

    def _require_context(
        self,
        *,
        source_file: Path,
        source_page: int,
        source_table: int,
        row_index: int,
        throughput_date: date | None,
        hour: time | None,
        airport_code: str | None,
    ) -> None:
        missing = []
        if throughput_date is None:
            missing.append("date context")
        if hour is None:
            missing.append("hour context")
        if airport_code is None:
            missing.append("airport context")

        if missing:
            raise self._row_error(
                source_file,
                source_page,
                source_table,
                row_index,
                f"missing {', '.join(missing)}",
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


def _clean_cell(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).replace("\n", " ")
    text = " ".join(text.split()).strip()
    return text or None


def _normalize_header_cell(value: str | None) -> str:
    return (value or "").casefold()


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError as exc:
        raise ParseError(f"could not parse date {value!r}") from exc


def _parse_hour(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ParseError(f"could not parse hour {value!r}") from exc


def _parse_count(value: str) -> int:
    if not re.fullmatch(r"[\d,]+", value):
        raise ParseError(f"could not parse throughput count {value!r}")
    return int(value.replace(",", ""))
