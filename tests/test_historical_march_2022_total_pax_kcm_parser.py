from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

march_parser = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber"
)
METRIC_NAME = march_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = march_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = march_parser.PARSER_NAME
HistoricalMarch2022Parser = (
    march_parser.HistoricalMarch2022TotalPaxKcmHourlyCheckpointPdfplumberParser
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2022-03-26.pdf")
BOUNDARY_FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2022-03-05.pdf")


def test_historical_march_2022_parser_parses_fixture() -> None:
    parser = HistoricalMarch2022Parser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2022, 3, 20)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 168
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_march_2022_parser_forward_fills_metadata() -> None:
    parser = HistoricalMarch2022Parser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    dca_concourse_a = next(
        record
        for record in result.records
        if record.airport_code == "DCA" and record.checkpoint_name == "Concourse A"
    )

    assert dca_concourse_a.throughput_date == date(2022, 3, 20)
    assert dca_concourse_a.hour == time(0, 0)
    assert dca_concourse_a.airport_name == "Washington Reagan National"
    assert dca_concourse_a.city == "Arlington"
    assert dca_concourse_a.state == "VA"
    assert dca_concourse_a.throughput_count == 6


def test_historical_march_2022_parser_parses_start_boundary_fixture() -> None:
    parser = HistoricalMarch2022Parser()

    result = parser.parse(BOUNDARY_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2022, 2, 27)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 391
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_march_2022_parser_rejects_pmis_header() -> None:
    parser = HistoricalMarch2022Parser()
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
            "3/20/2022",
            "00:00",
            "ANC",
            "Ted Stevens Anchorage International",
            "Anchorage",
            "AK",
            "South Checkpoint",
            None,
            "168",
        ],
    ]

    with pytest.raises(ParseError, match="expected 8 columns, found 9"):
        parser.parse_table(table, source_file=Path("bad.pdf"), source_page=1, source_table=1)
