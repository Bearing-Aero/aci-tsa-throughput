"""Parser for legacy PMIS PDFs with split year date cells."""

from __future__ import annotations

import re
from datetime import date

from tsa_throughput.exceptions import ParseError
from tsa_throughput.parsing.plugins import (
    historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber as pmis_parser,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    _parse_date,
)

PARSER_NAME = "historical_legacy_pmis_split_year_dates_pdfplumber"
PARSER_VERSION = "0.1.0"
LAYOUT_FAMILY = "hourly_checkpoint_pmis_total_customer_throughput_split_year_dates"
METRIC_NAME = pmis_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = pmis_parser.METRIC_SOURCE_COLUMN
PARSE_CONFIDENCE = pmis_parser.PARSE_CONFIDENCE

_SPLIT_YEAR_PATTERN = re.compile(r"(?<=/\d{3})\s+(?=\d$)")
_REPAIRED_DATE_PATTERN = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")


class HistoricalLegacyPmisSplitYearDatesPdfplumberParser(
    pmis_parser.HistoricalPmisTotalCustomerThroughputHourlyCheckpointPdfplumberParser
):
    """Parse legacy PMIS tables whose year digits can be split across lines."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY

    def _parse_date(self, value: str) -> date:
        try:
            return _parse_date(value)
        except ParseError as exc:
            repaired_value = _SPLIT_YEAR_PATTERN.sub("", value)
            if repaired_value == value or not _REPAIRED_DATE_PATTERN.fullmatch(
                repaired_value
            ):
                raise exc

            try:
                return _parse_date(repaired_value)
            except ParseError as repaired_exc:
                raise ParseError(f"could not parse date {value!r}") from repaired_exc
