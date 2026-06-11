"""Parser for early historical PMIS PDFs with Hour of Day headers."""

from __future__ import annotations

from tsa_throughput.parsing.plugins import (
    historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber as pmis_parser,
)

PARSER_NAME = "historical_early_hour_of_day_pmis_pdfplumber"
PARSER_VERSION = "0.1.0"
LAYOUT_FAMILY = "hourly_checkpoint_pmis_total_customer_throughput_early_hour_of_day"
METRIC_NAME = pmis_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = pmis_parser.METRIC_SOURCE_COLUMN
PARSE_CONFIDENCE = pmis_parser.PARSE_CONFIDENCE


class HistoricalEarlyHourOfDayPmisPdfplumberParser(
    pmis_parser.HistoricalPmisTotalCustomerThroughputHourlyCheckpointPdfplumberParser
):
    """Parse early PMIS hourly tables that retain the `Hour of Day` header."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY
