"""Parser for historical PMIS PDFs whose hour header is shortened to Hour."""

from __future__ import annotations

from pathlib import Path

from tsa_throughput.parsing.plugins import (
    historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber as pmis_parser,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    _normalize_header_cell,
)

PARSER_NAME = "historical_hour_header_pmis_pdfplumber"
PARSER_VERSION = "0.1.0"
LAYOUT_FAMILY = "hourly_checkpoint_pmis_total_customer_throughput_hour_header"
METRIC_NAME = pmis_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = pmis_parser.METRIC_SOURCE_COLUMN
PARSE_CONFIDENCE = pmis_parser.PARSE_CONFIDENCE
EXPECTED_COLUMN_COUNT = pmis_parser.EXPECTED_COLUMN_COUNT


class HistoricalHourHeaderPmisPdfplumberParser(
    pmis_parser.HistoricalPmisTotalCustomerThroughputHourlyCheckpointPdfplumberParser
):
    """Parse PMIS hourly tables whose second header cell is `Hour`."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY

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
            1: "hour",
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
                        f"unexpected hour-header PMIS header at column {index}: "
                        f"expected {expected_value!r}, found {header[index]!r}"
                    ),
                )
