from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

pmis_parser = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber"
)
METRIC_NAME = pmis_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = pmis_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = pmis_parser.PARSER_NAME
PmisParser = (
    pmis_parser.HistoricalPmisTotalCustomerThroughputHourlyCheckpointPdfplumberParser
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2022-04-02.pdf")
EARLY_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2022-02-26.pdf"
)
START_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2022-01-08.pdf"
)


def test_historical_pmis_parser_parses_fixture() -> None:
    parser = PmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2022, 3, 27)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 165
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_pmis_parser_forward_fills_metadata() -> None:
    parser = PmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    dca_north = next(
        record
        for record in result.records
        if record.airport_code == "DCA" and record.checkpoint_name == "North Checkpoint"
    )

    assert dca_north.throughput_date == date(2022, 3, 27)
    assert dca_north.hour == time(0, 0)
    assert dca_north.airport_name == "Washington Reagan National"
    assert dca_north.city == "Arlington"
    assert dca_north.state == "VA"
    assert dca_north.throughput_count == 2


def test_historical_pmis_parser_parses_early_boundary_fixture() -> None:
    parser = PmisParser()

    result = parser.parse(EARLY_BOUNDARY_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2022, 2, 20)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ABQ"
    assert first_record.airport_name == "Albuquerque International Sunport"
    assert first_record.city == "Albuquerque"
    assert first_record.state == "NM"
    assert first_record.checkpoint_name == "Checkpoint for A/B Gates"
    assert first_record.throughput_count == 10
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_pmis_parser_parses_start_boundary_fixture() -> None:
    parser = PmisParser()

    result = parser.parse(START_BOUNDARY_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2022, 1, 2)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 281
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_pmis_parser_forward_fills_early_boundary_metadata() -> None:
    parser = PmisParser()

    result = parser.parse(EARLY_BOUNDARY_FIXTURE_PDF, max_pages=3)
    dca_north = next(
        record
        for record in result.records
        if record.airport_code == "DCA" and record.checkpoint_name == "North Checkpoint"
    )

    assert dca_north.throughput_date == date(2022, 2, 20)
    assert dca_north.hour == time(0, 0)
    assert dca_north.airport_name == "Washington Reagan National"
    assert dca_north.city == "Arlington"
    assert dca_north.state == "VA"
    assert dca_north.throughput_count == 0


def test_historical_pmis_parser_rejects_total_pax_header() -> None:
    parser = PmisParser()
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
        ["3/20/2022", "00:00", "ANC", "Airport", "Anchorage", "AK", "South", "168"],
    ]

    with pytest.raises(ParseError, match="expected 9 columns, found 8"):
        parser.parse_table(table, source_file=Path("bad.pdf"), source_page=1, source_table=1)
