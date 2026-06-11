from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

early_hour_of_day_parser = import_module(
    "tsa_throughput.parsing.plugins.historical_early_hour_of_day_pmis_pdfplumber"
)
METRIC_NAME = early_hour_of_day_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = early_hour_of_day_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = early_hour_of_day_parser.PARSER_NAME
EarlyHourOfDayPmisParser = (
    early_hour_of_day_parser.HistoricalEarlyHourOfDayPmisPdfplumberParser
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2017-02-04.pdf")


def test_historical_early_hour_of_day_pmis_parser_parses_fixture() -> None:
    parser = EarlyHourOfDayPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2017, 1, 15)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 197
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_early_hour_of_day_pmis_parser_forward_fills_metadata() -> None:
    parser = EarlyHourOfDayPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    dtw_red = next(
        record
        for record in result.records
        if record.airport_code == "DTW" and record.checkpoint_name == "Red 3"
    )

    assert dtw_red.throughput_date == date(2017, 1, 15)
    assert dtw_red.hour == time(0, 0)
    assert dtw_red.airport_name == "Detroit Metro Wayne County"
    assert dtw_red.city == "Detroit"
    assert dtw_red.state == "MI"
    assert dtw_red.throughput_count == 9


def test_historical_early_hour_of_day_pmis_parser_updates_hour_context() -> None:
    parser = EarlyHourOfDayPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    late_record = result.records[-1]

    assert late_record.throughput_date == date(2017, 1, 15)
    assert late_record.hour == time(3, 0)
    assert late_record.airport_code == "DFW"
    assert late_record.airport_name == "Dallas/Fort Worth International"
    assert late_record.city == "DFW Airport"
    assert late_record.state == "TX"
    assert late_record.checkpoint_name == "E18"
    assert late_record.throughput_count == 60


def test_historical_early_hour_of_day_pmis_parser_rejects_hour_header() -> None:
    parser = EarlyHourOfDayPmisParser()
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
