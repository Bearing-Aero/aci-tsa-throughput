"""Parser for March 2022 TSA hourly checkpoint throughput PDFs."""

from __future__ import annotations

from tsa_throughput.parsing.plugins import (
    modern_total_pax_kcm_hourly_checkpoint_pdfplumber as modern_parser,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser,
)

LAYOUT_FAMILY = "hourly_checkpoint_total_pax_kcm_march_2022"
METRIC_NAME = modern_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = modern_parser.METRIC_SOURCE_COLUMN
PARSE_CONFIDENCE = modern_parser.PARSE_CONFIDENCE

PARSER_NAME = "historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber"
PARSER_VERSION = "0.1.0"


class HistoricalMarch2022TotalPaxKcmHourlyCheckpointPdfplumberParser(
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser
):
    """Parse March 2022 PDFs with the Total Pax + KCM PAX layout."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY
