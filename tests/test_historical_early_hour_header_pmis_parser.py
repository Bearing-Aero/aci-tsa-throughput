from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

early_hour_header_parser = import_module(
    "tsa_throughput.parsing.plugins.historical_early_hour_header_pmis_pdfplumber"
)
METRIC_NAME = early_hour_header_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = early_hour_header_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = early_hour_header_parser.PARSER_NAME
EarlyHourHeaderPmisParser = (
    early_hour_header_parser.HistoricalEarlyHourHeaderPmisPdfplumberParser
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2017-01-28.pdf")
START_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2017-01-21.pdf"
)


def test_historical_early_hour_header_pmis_parser_parses_fixture() -> None:
    parser = EarlyHourHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2017, 1, 22)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 133
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_early_hour_header_pmis_parser_forward_fills_metadata() -> None:
    parser = EarlyHourHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    dtw_blue = next(
        record
        for record in result.records
        if record.airport_code == "DTW" and record.checkpoint_name == "Blue-2"
    )

    assert dtw_blue.throughput_date == date(2017, 1, 22)
    assert dtw_blue.hour == time(0, 0)
    assert dtw_blue.airport_name == "Detroit Metro Wayne County"
    assert dtw_blue.city == "Detroit"
    assert dtw_blue.state == "MI"
    assert dtw_blue.throughput_count == 18


def test_historical_early_hour_header_pmis_parser_updates_hour_context() -> None:
    parser = EarlyHourHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    late_record = result.records[-1]

    assert late_record.throughput_date == date(2017, 1, 22)
    assert late_record.hour == time(3, 0)
    assert late_record.airport_code == "DFW"
    assert late_record.airport_name == "Dallas/Fort Worth International"
    assert late_record.city == "DFW Airport"
    assert late_record.state == "TX"
    assert late_record.checkpoint_name == "C21"
    assert late_record.throughput_count == 139


def test_historical_early_hour_header_pmis_parser_parses_start_boundary() -> None:
    parser = EarlyHourHeaderPmisParser()

    result = parser.parse(START_BOUNDARY_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2017, 1, 15)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Anchorage International"
    assert first_record.throughput_count == 197
    assert first_record.parser_name == PARSER_NAME


def test_historical_early_hour_header_pmis_parser_rejects_hour_of_day_header() -> None:
    parser = EarlyHourHeaderPmisParser()
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
