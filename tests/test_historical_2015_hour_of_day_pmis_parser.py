from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

historical_2015_parser = import_module(
    "tsa_throughput.parsing.plugins.historical_2015_hour_of_day_pmis_pdfplumber"
)
METRIC_NAME = historical_2015_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = historical_2015_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = historical_2015_parser.PARSER_NAME
Historical2015HourOfDayPmisParser = (
    historical_2015_parser.Historical2015HourOfDayPmisPdfplumberParser
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2015-01-27.pdf")
START_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2015-01-10.pdf"
)


def test_historical_2015_hour_of_day_pmis_parser_parses_fixture() -> None:
    parser = Historical2015HourOfDayPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2015, 1, 21)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 69
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_2015_hour_of_day_pmis_parser_forward_fills_metadata() -> None:
    parser = Historical2015HourOfDayPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    dtw_red = next(
        record
        for record in result.records
        if record.airport_code == "DTW" and record.checkpoint_name == "Red 3"
    )

    assert dtw_red.throughput_date == date(2015, 1, 21)
    assert dtw_red.hour == time(0, 0)
    assert dtw_red.airport_name == "Detroit Metro Wayne County"
    assert dtw_red.city == "Detroit"
    assert dtw_red.state == "MI"
    assert dtw_red.throughput_count == 3


def test_historical_2015_hour_of_day_pmis_parser_updates_hour_context() -> None:
    parser = Historical2015HourOfDayPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    late_record = result.records[-1]

    assert late_record.throughput_date == date(2015, 1, 21)
    assert late_record.hour == time(3, 0)
    assert late_record.airport_code == "IND"
    assert late_record.airport_name == "Indianapolis International"
    assert late_record.city == "Indianapolis"
    assert late_record.state == "IN"
    assert late_record.checkpoint_name == "Checkpoint B"
    assert late_record.throughput_count == 28


def test_historical_2015_hour_of_day_pmis_parser_parses_start_boundary() -> None:
    parser = Historical2015HourOfDayPmisParser()

    result = parser.parse(START_BOUNDARY_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2015, 1, 4)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.throughput_count == 416
    assert first_record.parser_name == PARSER_NAME


def test_historical_2015_hour_of_day_pmis_parser_rejects_hour_header() -> None:
    parser = Historical2015HourOfDayPmisParser()
    table = [
        [
            "Date",
            "Hour",
            "Airport",
            None,
            "City",
            "State",
            "Checkpoint",
            "Metrics",
            "PMIS - Total Customer Throughput (Unadjusted)",
        ],
        [
            "1/22/2017",
            "00:00",
            "ANC",
            "Anchorage International",
            "Anchorage",
            "AK",
            "South Checkpoint",
            None,
            "133",
        ],
    ]

    with pytest.raises(ParseError, match="expected 'hour of day'"):
        parser.parse_table(
            table,
            source_file=Path("bad.pdf"),
            source_page=1,
            source_table=1,
        )
