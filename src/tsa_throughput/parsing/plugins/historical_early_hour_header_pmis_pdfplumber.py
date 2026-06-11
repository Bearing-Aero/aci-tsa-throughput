"""Parser for early historical PMIS PDFs whose hour header is shortened."""

from __future__ import annotations

from tsa_throughput.parsing.plugins import (
    historical_hour_header_pmis_pdfplumber as hour_header_parser,
)

PARSER_NAME = "historical_early_hour_header_pmis_pdfplumber"
PARSER_VERSION = "0.1.0"
LAYOUT_FAMILY = "hourly_checkpoint_pmis_total_customer_throughput_early_hour_header"
METRIC_NAME = hour_header_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = hour_header_parser.METRIC_SOURCE_COLUMN
PARSE_CONFIDENCE = hour_header_parser.PARSE_CONFIDENCE


class HistoricalEarlyHourHeaderPmisPdfplumberParser(
    hour_header_parser.HistoricalHourHeaderPmisPdfplumberParser
):
    """Parse early PMIS hourly tables whose second header cell is `Hour`."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY
