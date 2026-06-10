from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

legacy_pmis_parser = import_module(
    "tsa_throughput.parsing.plugins.historical_legacy_pmis_split_year_dates_pdfplumber"
)
METRIC_NAME = legacy_pmis_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = legacy_pmis_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = legacy_pmis_parser.PARSER_NAME
LegacyPmisParser = legacy_pmis_parser.HistoricalLegacyPmisSplitYearDatesPdfplumberParser

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2022-01-01.pdf")
START_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2018-07-07.pdf"
)


def test_historical_legacy_pmis_parser_parses_split_year_fixture() -> None:
    parser = LegacyPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2021, 12, 26)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 200
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_legacy_pmis_parser_forward_fills_metadata() -> None:
    parser = LegacyPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    dca_north = next(
        record
        for record in result.records
        if record.airport_code == "DCA" and record.checkpoint_name == "North Checkpoint"
    )

    assert dca_north.throughput_date == date(2021, 12, 26)
    assert dca_north.hour == time(0, 0)
    assert dca_north.airport_name == "Washington Reagan National"
    assert dca_north.city == "Arlington"
    assert dca_north.state == "VA"
    assert dca_north.throughput_count == 0


def test_historical_legacy_pmis_parser_parses_start_boundary_fixture() -> None:
    parser = LegacyPmisParser()

    result = parser.parse(START_BOUNDARY_FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2018, 7, 1)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ABQ"
    assert first_record.airport_name == "Albuquerque International Sunport"
    assert first_record.city == "Albuquerque"
    assert first_record.state == "NM"
    assert first_record.checkpoint_name == "Checkpoint for A/B Gates"
    assert first_record.throughput_count == 1
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_legacy_pmis_parser_rejects_merged_header_layout() -> None:
    parser = LegacyPmisParser()
    table = [
        [
            "Date",
            "Day",
            "Airport ABQ Albuquerque International Sunport",
            None,
            "City Albuquerque",
            "State NM",
            "Checkpoint Checkpoint for A/B Gates",
            "Metrics",
            "Throughput (Unadjusted) 1",
        ],
        [None, None, "ANC", "Airport", "Anchorage", "AK", "South", None, "287"],
    ]

    with pytest.raises(ParseError, match="unexpected header at column 1"):
        parser.parse_table(table, source_file=Path("bad.pdf"), source_page=1, source_table=1)
