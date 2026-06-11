from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

embedded_hour_parser = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_embedded_hour_merged_header_pmis_pdfplumber"
)
METRIC_NAME = embedded_hour_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = embedded_hour_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = embedded_hour_parser.PARSER_NAME
EmbeddedHourMergedHeaderPmisParser = (
    embedded_hour_parser.HistoricalEmbeddedHourMergedHeaderPmisPdfplumberParser
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2017-10-14.pdf")


def test_historical_embedded_hour_merged_header_pmis_parser_parses_fixture() -> None:
    parser = EmbeddedHourMergedHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2017, 10, 8)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ANC"
    assert first_record.airport_name == "Ted Stevens Anchorage International"
    assert first_record.city == "Anchorage"
    assert first_record.state == "AK"
    assert first_record.checkpoint_name == "South Checkpoint"
    assert first_record.throughput_count == 98
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_embedded_hour_merged_header_pmis_parser_forward_fills_metadata() -> None:
    parser = EmbeddedHourMergedHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    dtw_red = next(
        record
        for record in result.records
        if record.airport_code == "DTW" and record.checkpoint_name == "Red 3"
    )

    assert dtw_red.throughput_date == date(2017, 10, 8)
    assert dtw_red.hour == time(0, 0)
    assert dtw_red.airport_name == "Detroit Metro Wayne County"
    assert dtw_red.city == "Detroit"
    assert dtw_red.state == "MI"
    assert dtw_red.throughput_count == 11


def test_historical_embedded_hour_merged_header_pmis_parser_updates_hour_context() -> None:
    parser = EmbeddedHourMergedHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    late_record = result.records[-1]

    assert late_record.throughput_date == date(2017, 10, 8)
    assert late_record.hour == time(2, 0)
    assert late_record.airport_code == "MIA"
    assert late_record.airport_name == "Miami International"
    assert late_record.city == "Miami"
    assert late_record.state == "FL"
    assert late_record.checkpoint_name == "MIA-JC"
    assert late_record.throughput_count == 59


def test_historical_embedded_hour_merged_header_pmis_parser_rejects_plain_day_header() -> None:
    parser = EmbeddedHourMergedHeaderPmisParser()
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

    with pytest.raises(ParseError, match="embedded-hour merged-header PMIS layout"):
        parser._data_rows_from_table(
            table,
            source_file=Path("bad.pdf"),
            source_page=1,
            source_table=1,
        )
