from datetime import date, time
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError
from tsa_throughput.parsing.base import ThroughputParser
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    METRIC_NAME,
    METRIC_SOURCE_COLUMN,
    PARSE_CONFIDENCE,
    PARSER_NAME,
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser,
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf")
HISTORICAL_MODERN_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2025-12-27.pdf"
)


def test_modern_parser_can_parse_first_five_pages() -> None:
    parser = ModernTotalPaxKcmHourlyCheckpointPdfplumberParser()

    result = parser.parse(FIXTURE_PDF, max_pages=5)

    assert isinstance(parser, ThroughputParser)
    assert result.record_count > 0
    assert result.record_count == len(result.records)


def test_modern_parser_first_record_matches_expected_values() -> None:
    parser = ModernTotalPaxKcmHourlyCheckpointPdfplumberParser()

    result = parser.parse(FIXTURE_PDF, max_pages=5)
    first_record = result.records[0]

    assert first_record.throughput_date == date(2026, 5, 31)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 208
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME
    assert first_record.parse_confidence == PARSE_CONFIDENCE


def test_modern_parser_parses_verified_2025_boundary_fixture() -> None:
    parser = ModernTotalPaxKcmHourlyCheckpointPdfplumberParser()

    result = parser.parse(HISTORICAL_MODERN_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2025, 12, 21)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 288
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME
    assert first_record.parse_confidence == PARSE_CONFIDENCE


def test_modern_parser_forward_fills_verified_2025_boundary_fixture() -> None:
    parser = ModernTotalPaxKcmHourlyCheckpointPdfplumberParser()

    result = parser.parse(HISTORICAL_MODERN_FIXTURE_PDF, max_pages=3)
    atl_main = next(
        record
        for record in result.records
        if record.airport_code == "ATL" and record.checkpoint_name == "Main Checkpoint"
    )

    assert atl_main.throughput_date == date(2025, 12, 21)
    assert atl_main.hour == time(0, 0)
    assert atl_main.airport_name == "Hartsfield - Jackson Atlanta International"
    assert atl_main.city == "Atlanta"
    assert atl_main.state == "GA"
    assert atl_main.throughput_count == 88


def test_modern_parser_forward_fills_atl_metadata() -> None:
    parser = ModernTotalPaxKcmHourlyCheckpointPdfplumberParser()

    result = parser.parse(FIXTURE_PDF, max_pages=5)
    atl_main = next(
        record
        for record in result.records
        if record.airport_code == "ATL" and record.checkpoint_name == "Main Checkpoint"
    )

    assert atl_main.airport_name == "Hartsfield - Jackson Atlanta International"
    assert atl_main.city == "Atlanta"
    assert atl_main.state == "GA"
    assert atl_main.throughput_count == 79


def test_modern_parser_rejects_unrecognized_header() -> None:
    parser = ModernTotalPaxKcmHourlyCheckpointPdfplumberParser()
    table = [
        ["Hour", "Metrics", "Airport", None, "City", "State", "Checkpoint", "Count"],
        ["00:00", "Total", "ANC", "Airport", "Anchorage", "AK", "South", "1"],
    ]

    with pytest.raises(ParseError, match="unexpected header"):
        parser.parse_table(table, source_file=Path("bad.pdf"), source_page=1, source_table=1)


def test_modern_parser_does_not_forward_fill_checkpoint_name() -> None:
    parser = ModernTotalPaxKcmHourlyCheckpointPdfplumberParser()
    table = [
        [
            "Date",
            "Hour of Day",
            "Airport",
            None,
            "City",
            "State",
            "Checkpoint",
            "Total Pax + KCM PAX",
        ],
        [
            "5/31/2026",
            "00:00",
            "ANC",
            "Ted Stevens Anchorage International",
            "Anchorage",
            "AK",
            "South Checkpoint",
            "208",
        ],
        [None, None, None, None, None, None, None, "79"],
    ]

    with pytest.raises(ParseError, match="missing checkpoint"):
        parser.parse_table(table, source_file=Path("bad.pdf"), source_page=1, source_table=1)


def test_modern_parser_does_not_forward_fill_throughput_count() -> None:
    parser = ModernTotalPaxKcmHourlyCheckpointPdfplumberParser()
    table = [
        [
            "Date",
            "Hour of Day",
            "Airport",
            None,
            "City",
            "State",
            "Checkpoint",
            "Total Pax + KCM PAX",
        ],
        [
            "5/31/2026",
            "00:00",
            "ANC",
            "Ted Stevens Anchorage International",
            "Anchorage",
            "AK",
            "South Checkpoint",
            "208",
        ],
        [None, None, None, None, None, None, "Main Checkpoint", None],
    ]

    with pytest.raises(ParseError, match="missing throughput count"):
        parser.parse_table(table, source_file=Path("bad.pdf"), source_page=1, source_table=1)
