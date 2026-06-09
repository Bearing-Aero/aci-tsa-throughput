"""Parser for historical TSA PMIS hourly checkpoint throughput PDFs."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import Any

from tsa_throughput.exceptions import ParseError
from tsa_throughput.models import ThroughputRecord, ThroughputReport
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser,
    _clean_cell,
    _normalize_header_cell,
    _parse_count,
    _parse_date,
    _parse_hour,
)

PARSER_NAME = "historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber"
PARSER_VERSION = "0.1.0"
LAYOUT_FAMILY = "hourly_checkpoint_pmis_total_customer_throughput"
METRIC_NAME = "pmis_total_customer_throughput_unadjusted"
METRIC_SOURCE_COLUMN = "PMIS - Total Customer Throughput (Unadjusted)"
PARSE_CONFIDENCE = "high"

EXPECTED_COLUMN_COUNT = 9


class HistoricalPmisTotalCustomerThroughputHourlyCheckpointPdfplumberParser(
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser
):
    """Parse historical PMIS hourly airport/checkpoint throughput tables."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY

    def parse_table(
        self,
        table: list[list[Any]],
        *,
        source_file: Path,
        source_page: int,
        source_table: int,
        report: ThroughputReport | None = None,
    ) -> list[ThroughputRecord]:
        """Parse one extracted PMIS-layout table into throughput records."""
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
            7: "metrics",
            8: "pmis - total customer throughput (unadjusted)",
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
