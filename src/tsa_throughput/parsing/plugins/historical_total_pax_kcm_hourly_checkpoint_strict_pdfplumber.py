"""Parser for historical TSA hourly checkpoint PDFs requiring strict line extraction."""

from __future__ import annotations

from typing import Any

from tsa_throughput.parsing.plugins import (
    modern_total_pax_kcm_hourly_checkpoint_pdfplumber as modern_parser,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser,
)

PARSER_NAME = "historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber"
PARSER_VERSION = "0.1.0"
LAYOUT_FAMILY = "hourly_checkpoint_total_pax_kcm_strict_lines"
METRIC_NAME = modern_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = modern_parser.METRIC_SOURCE_COLUMN
PARSE_CONFIDENCE = modern_parser.PARSE_CONFIDENCE

STRICT_TABLE_SETTINGS: dict[str, Any] = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 1,
    "join_tolerance": 1,
    "intersection_tolerance": 1,
}


class HistoricalTotalPaxKcmHourlyCheckpointStrictPdfplumberParser(
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser
):
    """Parse 2022 Total Pax + KCM PAX PDFs with strict line extraction."""

    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    layout_family = LAYOUT_FAMILY
    table_settings = STRICT_TABLE_SETTINGS
