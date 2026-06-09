from datetime import date, time
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError
from tsa_throughput.parsing.plugins.historical_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    METRIC_NAME,
    METRIC_SOURCE_COLUMN,
    PARSER_NAME,
    HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser,
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2025-12-20.pdf")
BOUNDARY_FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2023-01-07.pdf")


def test_historical_total_pax_kcm_parser_parses_2025_boundary_fixture() -> None:
    parser = HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2025, 12, 14)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 130
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_total_pax_kcm_parser_forward_fills_metadata() -> None:
    parser = HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    atl_main = next(
        record
        for record in result.records
        if record.airport_code == "ATL" and record.checkpoint_name == "Main Checkpoint"
    )

    assert atl_main.throughput_date == date(2025, 12, 14)
    assert atl_main.hour == time(0, 0)
    assert atl_main.airport_name == "Hartsfield - Jackson Atlanta International"
    assert atl_main.city == "Atlanta"
    assert atl_main.state == "GA"
    assert atl_main.throughput_count == 45


def test_historical_total_pax_kcm_parser_parses_2023_start_boundary_fixture() -> None:
    parser = HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser()

    result = parser.parse(BOUNDARY_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2023, 1, 1)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_total_pax_kcm_parser_rejects_unrecognized_header() -> None:
    parser = HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser()
    table = [
        ["Hour", "Metrics", "Airport", None, "City", "State", "Checkpoint", "Count"],
        ["00:00", "Total", "ANC", "Airport", "Anchorage", "AK", "South", "1"],
    ]

    with pytest.raises(ParseError, match="unexpected header"):
        parser.parse_table(table, source_file=Path("bad.pdf"), source_page=1, source_table=1)
