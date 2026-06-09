"""Parser for historical TSA hourly checkpoint throughput PDFs."""

from __future__ import annotations

from tsa_throughput.parsing.plugins import (
    modern_total_pax_kcm_hourly_checkpoint_pdfplumber as modern_parser,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser,
)

LAYOUT_FAMILY = modern_parser.LAYOUT_FAMILY
METRIC_NAME = modern_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = modern_parser.METRIC_SOURCE_COLUMN
PARSE_CONFIDENCE = modern_parser.PARSE_CONFIDENCE

PARSER_NAME = "historical_total_pax_kcm_hourly_checkpoint_pdfplumber"
PARSER_VERSION = "0.1.0"


class HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser(
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser
):
    """Parse 2023-2025 historical PDFs with the Total Pax + KCM PAX layout."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY
