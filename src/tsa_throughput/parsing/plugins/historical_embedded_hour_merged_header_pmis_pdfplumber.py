"""Parser for historical PMIS PDFs with an embedded-hour merged header."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tsa_throughput.exceptions import ParseError
from tsa_throughput.parsing.plugins import (
    historical_merged_header_pmis_pdfplumber as merged_header_pmis_parser,
)
from tsa_throughput.parsing.plugins.historical_merged_header_pmis_pdfplumber import (
    EXPECTED_COLUMN_COUNT,
    HistoricalMergedHeaderPmisPdfplumberParser,
    _normalized_startswith,
    _strip_prefixed_value,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    _normalize_header_cell,
    _parse_hour,
)

PARSER_NAME = "historical_embedded_hour_merged_header_pmis_pdfplumber"
PARSER_VERSION = "0.1.0"
LAYOUT_FAMILY = "hourly_checkpoint_pmis_total_customer_throughput_embedded_hour_merged_header"
METRIC_NAME = merged_header_pmis_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = merged_header_pmis_parser.METRIC_SOURCE_COLUMN
PARSE_CONFIDENCE = merged_header_pmis_parser.PARSE_CONFIDENCE

_AIRPORT_CODE_PATTERN = re.compile(r"\b(?P<airport_code>[A-Z0-9]{3})\b")


class HistoricalEmbeddedHourMergedHeaderPmisPdfplumberParser(
    HistoricalMergedHeaderPmisPdfplumberParser
):
    """Parse a PMIS table whose first data row merges hour and airport into headers."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY

    def _data_rows_from_table(
        self,
        table: list[list[Any]],
        *,
        source_file: Path,
        source_page: int,
        source_table: int,
    ) -> list[list[str | None]]:
        rows = super()._data_rows_from_table(
            table,
            source_file=source_file,
            source_page=source_page,
            source_table=source_table,
        )
        first_row = rows[0] if rows else []
        if first_row and first_row[0] == "Date" and _normalized_startswith(
            first_row[1], "day"
        ):
            raise self._error(
                source_file=source_file,
                source_page=source_page,
                source_table=source_table,
                reason="embedded-hour merged-header PMIS layout not found",
            )
        return rows

    def _is_merged_header_row(self, row: list[str | None]) -> bool:
        if len(row) != EXPECTED_COLUMN_COUNT:
            return False

        return (
            _normalize_header_cell(row[0]) == "date"
            and _normalized_startswith(row[1], "day ")
            and _is_day_hour_cell(row[1])
            and _normalized_startswith(row[2], "airport ")
            and row[3] is None
            and _normalized_startswith(row[4], "city ")
            and _normalized_startswith(row[5], "state ")
            and _normalized_startswith(row[6], "checkpoint ")
            and _normalize_header_cell(row[7]) == "metrics"
            and _normalized_startswith(row[8], "throughput (unadjusted) ")
        )

    def _row_from_merged_header(self, row: list[str | None]) -> list[str | None]:
        airport_code, airport_name = _split_airport_header_value(
            _strip_prefixed_value(row[2], "Airport")
        )

        return [
            None,
            _strip_prefixed_value(row[1], "Day"),
            airport_code,
            airport_name,
            _strip_prefixed_value(row[4], "City"),
            _strip_prefixed_value(row[5], "State"),
            _strip_prefixed_value(row[6], "Checkpoint"),
            None,
            _strip_prefixed_value(row[8], "Throughput (Unadjusted)"),
        ]


def _is_day_hour_cell(value: str | None) -> bool:
    if value is None:
        return False

    try:
        _parse_hour(_strip_prefixed_value(value, "Day"))
    except ParseError:
        return False
    return True


def _split_airport_header_value(value: str) -> tuple[str, str]:
    matches = list(_AIRPORT_CODE_PATTERN.finditer(value))
    if not matches:
        raise ParseError(f"missing airport code in merged airport header: {value!r}")

    match = matches[-1]
    airport_code = match.group("airport_code")
    airport_name = f"{value[: match.start()]} {value[match.end() :]}".strip()
    airport_name = " ".join(airport_name.split())
    if not airport_name:
        raise ParseError(f"missing airport name in merged airport header: {value!r}")

    return airport_code, airport_name
