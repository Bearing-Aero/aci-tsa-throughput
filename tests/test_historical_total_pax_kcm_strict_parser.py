from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

strict_parser = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber"
)
METRIC_NAME = strict_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = strict_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = strict_parser.PARSER_NAME
StrictParser = (
    strict_parser.HistoricalTotalPaxKcmHourlyCheckpointStrictPdfplumberParser
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2022-12-31.pdf")
BOUNDARY_FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2022-04-09.pdf")


def test_historical_total_pax_kcm_strict_parser_parses_2022_boundary_fixture() -> None:
    parser = StrictParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2022, 12, 25)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 203
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_total_pax_kcm_strict_parser_forward_fills_metadata() -> None:
    parser = StrictParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    dca_north = next(
        record
        for record in result.records
        if record.airport_code == "DCA" and record.checkpoint_name == "North Checkpoint"
    )

    assert dca_north.throughput_date == date(2022, 12, 25)
    assert dca_north.hour == time(0, 0)
    assert dca_north.airport_name == "Washington Reagan National"
    assert dca_north.city == "Arlington"
    assert dca_north.state == "VA"
    assert dca_north.throughput_count == 3


def test_historical_total_pax_kcm_strict_parser_parses_start_boundary_fixture() -> None:
    parser = StrictParser()

    result = parser.parse(BOUNDARY_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2022, 4, 3)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 201
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_total_pax_kcm_strict_parser_rejects_unrecognized_header() -> None:
    parser = StrictParser()
    table = [
        [
            "Date",
            "Hour of Day",
            "Airport",
            None,
            "City",
            "State",
            "Checkpoint",
            "Metrics",
            "PMIS - Total Customer Throughput (Unadjusted)",
        ],
        ["3/27/2022", "00:00", "ANC", "Airport", "Anchorage", "AK", "South", None, "1"],
    ]

    with pytest.raises(ParseError, match="expected 8 columns, found 9"):
        parser.parse_table(table, source_file=Path("bad.pdf"), source_page=1, source_table=1)
