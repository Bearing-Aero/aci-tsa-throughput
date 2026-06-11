from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

hour_header_parser = import_module(
    "tsa_throughput.parsing.plugins.historical_hour_header_pmis_pdfplumber"
)
METRIC_NAME = hour_header_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = hour_header_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = hour_header_parser.PARSER_NAME
HourHeaderPmisParser = hour_header_parser.HistoricalHourHeaderPmisPdfplumberParser

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2017-10-07.pdf")
START_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2017-02-11.pdf"
)


def test_historical_hour_header_pmis_parser_parses_fixture() -> None:
    parser = HourHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2017, 10, 1)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 111
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_hour_header_pmis_parser_forward_fills_metadata() -> None:
    parser = HourHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    dtw_red = next(
        record
        for record in result.records
        if record.airport_code == "DTW" and record.checkpoint_name == "Red 3"
    )

    assert dtw_red.throughput_date == date(2017, 10, 1)
    assert dtw_red.hour == time(0, 0)
    assert dtw_red.airport_name == "Detroit Metro Wayne County"
    assert dtw_red.city == "Detroit"
    assert dtw_red.state == "MI"
    assert dtw_red.throughput_count == 10


def test_historical_hour_header_pmis_parser_updates_hour_context() -> None:
    parser = HourHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    late_record = result.records[-1]

    assert late_record.throughput_date == date(2017, 10, 1)
    assert late_record.hour == time(3, 0)
    assert late_record.airport_code == "HOU"
    assert late_record.airport_name == "Houston Hobby"
    assert late_record.city == "Houston"
    assert late_record.state == "TX"
    assert late_record.checkpoint_name == "CENTRAL"
    assert late_record.throughput_count == 14


def test_historical_hour_header_pmis_parser_parses_start_boundary_fixture() -> None:
    parser = HourHeaderPmisParser()

    result = parser.parse(START_BOUNDARY_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2017, 2, 5)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Anchorage International"
    assert first_record.throughput_count == 118
    assert first_record.parser_name == PARSER_NAME


def test_historical_hour_header_pmis_parser_rejects_hour_of_day_header() -> None:
    parser = HourHeaderPmisParser()
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
        [
            "1/15/2017",
            "00:00",
            "ANC",
            "Ted Stevens Anchorage International",
            "Anchorage",
            "AK",
            "South Checkpoint",
            None,
            "197",
        ],
    ]

    with pytest.raises(ParseError, match="unexpected hour-header PMIS header"):
        parser.parse_table(
            table,
            source_file=Path("bad.pdf"),
            source_page=1,
            source_table=1,
        )
